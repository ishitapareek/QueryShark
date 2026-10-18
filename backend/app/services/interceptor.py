import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from mysql.connector import Error
from app.core.config import settings
from app.db.connection import DatabasePool
from app.services.sql_parser import SQLParserService

logger = logging.getLogger(__name__)

class QueryInterceptorService:
    """
    Core interception service measuring query execution latency,
    evaluating threshold violations, persisting metrics to QueryRuns,
    and profiling multi-statement SQL batches.
    """

    @staticmethod
    def execute_and_intercept(
        sql_query: str,
        schema_name: str = "default"
    ) -> Tuple[Dict[str, Any], int, Optional[List[Any]], Optional[str]]:
        """
        Executes a single SQL query, captures precise wall-clock latency,
        determines SLA status (FAST/SLOW/ERROR), and logs to QueryRuns.
        """
        start_time = time.perf_counter()
        status = "FAST"
        results = None
        rows_affected = 0
        error_msg = None

        try:
            with DatabasePool.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if schema_name and schema_name != "default":
                    try:
                        cursor.execute(f"USE `{schema_name}`;")
                    except Error as se:
                        logger.warning(f"Could not switch schema to {schema_name}: {se}")

                cursor.execute(sql_query)

                if cursor.description:
                    results = cursor.fetchall()
                    rows_affected = len(results)
                else:
                    conn.commit()
                    rows_affected = cursor.rowcount
                cursor.close()
        except Error as err:
            logger.error(f"Database Query Error during interception: {err}")
            error_msg = str(err)
            status = "ERROR"
            results = [{"error": error_msg}]
        except Exception as ex:
            logger.error(f"Unexpected error executing query: {ex}")
            error_msg = str(ex)
            status = "ERROR"
            results = [{"error": error_msg}]

        elapsed_time_ms = round((time.perf_counter() - start_time) * 1000, 3)

        # If query succeeded, evaluate whether duration violates the slow threshold
        if status != "ERROR" and elapsed_time_ms > settings.SLOW_QUERY_THRESHOLD_MS:
            status = "SLOW"

        record = QueryInterceptorService._save_query_run(
            sql_text=sql_query,
            schema_name=schema_name,
            duration_ms=elapsed_time_ms,
            status=status if status in ("FAST", "SLOW") else "SLOW"
        )

        return record, rows_affected, results, error_msg

    @staticmethod
    def execute_batch_and_intercept(
        statements: List[str],
        schema_name: str = "default",
        rank_by: str = "duration_desc"
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Executes a series of SQL statements sequentially, intercepts each statement's
        performance metrics, logs runs, computes batch statistics, and ranks the statements.
        """
        executed_records: List[Dict[str, Any]] = []
        slow_count = 0
        fast_count = 0
        error_count = 0
        total_dur_ms = 0.0
        durations = []

        for index, stmt in enumerate(statements, start=1):
            stmt_clean = stmt.strip()
            if not stmt_clean:
                continue

            record, rows, results, error = QueryInterceptorService.execute_and_intercept(
                sql_query=stmt_clean,
                schema_name=schema_name
            )

            dur = record.get("duration_ms", 0.0)
            total_dur_ms += dur
            durations.append(dur)

            st_status = record.get("status", "FAST")
            if error:
                st_status = "ERROR"
                error_count += 1
            elif dur > settings.SLOW_QUERY_THRESHOLD_MS:
                st_status = "SLOW"
                slow_count += 1
            else:
                st_status = "FAST"
                fast_count += 1

            stmt_result = {
                "statement_index": index,
                "sql_text": stmt_clean,
                "duration_ms": dur,
                "status": st_status,
                "rows_affected": rows,
                "error": error,
                "timestamp": record.get("timestamp", datetime.now()),
                "queryID": record.get("queryID"),
                "rank": 0
            }
            executed_records.append(stmt_result)

        # Multi-criteria ranking
        ranked_records = SQLParserService.rank_statements(executed_records, rank_by=rank_by)

        total_stmts = len(executed_records)
        avg_dur = round(total_dur_ms / total_stmts, 3) if total_stmts > 0 else 0.0
        max_dur = max(durations) if durations else 0.0
        min_dur = min(durations) if durations else 0.0
        slow_pct = round((slow_count / total_stmts * 100), 2) if total_stmts > 0 else 0.0

        summary = {
            "total_statements": total_stmts,
            "successful_statements": total_stmts - error_count,
            "failed_statements": error_count,
            "slow_statements": slow_count,
            "fast_statements": fast_count,
            "total_duration_ms": round(total_dur_ms, 3),
            "avg_duration_ms": avg_dur,
            "max_duration_ms": round(max_dur, 3),
            "min_duration_ms": round(min_dur, 3),
            "slow_percentage": slow_pct
        }

        return summary, ranked_records

    @staticmethod
    def _save_query_run(sql_text: str, schema_name: str, duration_ms: float, status: str) -> dict:
        now = datetime.now()
        record_id = -1
        try:
            with DatabasePool.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                INSERT INTO QueryRuns (sql_text, current_schema, duration_ms, status, timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (sql_text, schema_name, duration_ms, status, now))
                conn.commit()
                record_id = cursor.lastrowid
                cursor.close()
        except Exception as e:
            logger.error(f"Failed to record query execution log: {e}")

        return {
            "queryID": record_id,
            "sql_text": sql_text,
            "current_schema": schema_name,
            "duration_ms": duration_ms,
            "status": status,
            "timestamp": now
        }