from fastapi import status
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from app.models.query_model import (
    QueryExecuteRequest,
    QueryExecuteResponse,
    QueryRunRecord,
    QuerySummaryStats,
    QueryRankingOption,
    BatchQueryExecuteResponse,
    BatchScriptExecuteRequest,
)
from app.services.interceptor import QueryInterceptorService
from app.services.sql_parser import SQLParserService
from app.services.performance_schema import PerformanceSchemaService
from app.db.connection import DatabasePool

router = APIRouter()

@router.post("/execute", response_model=QueryExecuteResponse)
def execute_query(payload: QueryExecuteRequest):
    """
    Executes a single SQL query, measures latency with high precision,
    records the run in QueryRuns, and returns execution metrics.
    """
    record, rows_affected, results, error = QueryInterceptorService.execute_and_intercept(
        sql_query=payload.sql_query,
        schema_name=payload.schema_name or "default"
    )
    return {
        "query_record": record,
        "rows_affected": rows_affected,
        "results": results,
        "error": error
    }

@router.post("/upload-sql", response_model=BatchQueryExecuteResponse)
async def upload_sql_file(
    file: UploadFile = File(..., description="SQL script file (.sql)"),
    schema_name: str = Form("default", description="Target database schema"),
    rank_by: QueryRankingOption = Form(
        QueryRankingOption.DURATION_DESC,
        description="Ranking criteria for returned statements"
    )
):
    """
    Uploads a .sql file, parses out individual statements, intercepts and executes
    each statement sequentially, computes statistical aggregates, and returns ranked results.
    """
    if not (file.filename.endswith(".sql") or file.filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only .sql or .txt files are supported.")

    try:
        raw_bytes = await file.read()
        try:
            sql_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            sql_text = raw_bytes.decode("latin-1")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    statements = SQLParserService.split_sql_statements(sql_text)
    if not statements:
        raise HTTPException(status_code=400, detail="No executable SQL statements found in uploaded file.")

    summary, ranked_records = QueryInterceptorService.execute_batch_and_intercept(
        statements=statements,
        schema_name=schema_name,
        rank_by=rank_by.value
    )

    return {
        "filename": file.filename,
        "ranking_criterion": rank_by.value,
        "summary": summary,
        "statements": ranked_records
    }

@router.post("/execute-script", response_model=BatchQueryExecuteResponse)
def execute_sql_script(payload: BatchScriptExecuteRequest):
    """
    Executes a raw multi-statement SQL script string, intercepts performance,
    and returns ranked metrics and summary.
    """
    statements = SQLParserService.split_sql_statements(payload.sql_script)
    if not statements:
        raise HTTPException(status_code=400, detail="No executable SQL statements found in script.")

    summary, ranked_records = QueryInterceptorService.execute_batch_and_intercept(
        statements=statements,
        schema_name=payload.schema_name or "default",
        rank_by=payload.rank_by.value
    )

    return {
        "filename": "raw_script.sql",
        "ranking_criterion": payload.rank_by.value,
        "summary": summary,
        "statements": ranked_records
    }

@router.get("/", response_model=List[QueryRunRecord])
def get_queries(
    status: Optional[str] = Query(None, description="Filter by FAST or SLOW"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    rank_by: QueryRankingOption = Query(
        QueryRankingOption.DURATION_DESC,
        description="Option to rank/order query records"
    ),
    sort_slowest: Optional[bool] = Query(None, description="Legacy parameter for backward compatibility")
):
    """
    Retrieves logged query runs with flexible ranking options and status filtering.
    """
    base_query = """
        SELECT
            queryID,
            sql_text,
            current_schema,
            duration_ms,
            total_elapsed_ms,
            status,
            timestamp
        FROM QueryRuns
    """
    params = []

    if status and status.upper() != "ALL":
        base_query += " WHERE status = %s"
        params.append(status.upper())

    # Determine sorting order based on rank_by or backward-compatible sort_slowest
    if sort_slowest is not None:
        if sort_slowest:
            base_query += " ORDER BY duration_ms DESC"
        else:
            base_query += " ORDER BY timestamp DESC"
    else:
        if rank_by == QueryRankingOption.DURATION_DESC:
            base_query += " ORDER BY duration_ms DESC"
        elif rank_by == QueryRankingOption.DURATION_ASC:
            base_query += " ORDER BY duration_ms ASC"
        elif rank_by == QueryRankingOption.TIMESTAMP_DESC:
            base_query += " ORDER BY timestamp DESC"
        elif rank_by == QueryRankingOption.TIMESTAMP_ASC:
            base_query += " ORDER BY timestamp ASC"
        elif rank_by == QueryRankingOption.STATUS:
            base_query += " ORDER BY status DESC, duration_ms DESC"
        else:
            base_query += " ORDER BY duration_ms DESC"

    base_query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    records = []
    with DatabasePool.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(base_query, tuple(params))
        records = cursor.fetchall()
        cursor.close()

    return records

@router.get("/slow", response_model=List[QueryRunRecord])
def get_top_slow_queries(limit: int = Query(10, ge=1, le=100)):
    """
    Retrieves the top slowest queries that breached the SLA threshold (>100ms).
    """
    query = """
    SELECT queryID, sql_text, current_schema, duration_ms, total_elapsed_ms, status, timestamp 
    FROM QueryRuns 
    WHERE status = 'SLOW' 
    ORDER BY duration_ms DESC 
    LIMIT %s
    """
    with DatabasePool.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, (limit,))
        records = cursor.fetchall()
        cursor.close()
    return records

@router.get("/summary", response_model=QuerySummaryStats)
def get_summary_stats():
    """
    Calculates aggregated telemetry metrics across all captured queries.
    """
    query = """
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'SLOW' THEN 1 ELSE 0 END) as slow_count,
        SUM(CASE WHEN status = 'FAST' THEN 1 ELSE 0 END) as fast_count,
        COALESCE(AVG(duration_ms), 0) as avg_duration
    FROM QueryRuns;
    """
    with DatabasePool.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        row = cursor.fetchone()
        cursor.close()

    total = row["total"] or 0
    slow = int(row["slow_count"] or 0)
    fast = int(row["fast_count"] or 0)
    avg_dur = round(float(row["avg_duration"] or 0.0), 2)
    pct = round((slow / total * 100), 2) if total > 0 else 0.0

    return {
        "total_queries": total,
        "slow_queries": slow,
        "fast_queries": fast,
        "avg_duration_ms": avg_dur,
        "slow_percentage": pct
    }

@router.get("/performance-schema")
def get_performance_schema_metrics(limit: int = Query(10, ge=1, le=50)):
    """
    Extracts deep database engine statistics directly from MySQL performance_schema.
    """
    is_active = PerformanceSchemaService.is_enabled()
    records = PerformanceSchemaService.get_top_digest_queries(limit=limit) if is_active else []
    return {
        "performance_schema_enabled": is_active,
        "top_digests": records
    }