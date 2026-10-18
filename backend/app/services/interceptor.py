import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from mysql.connector import Error
from app.core.config import settings
from app.db.connection import DatabasePool
from app.services.sql_parser import SQLParserService

logger = logging.getLogger(__name__)


def get_statement_baseline(cursor):
    """
    Get this connection's Performance Schema thread ID and the
    latest statement event currently visible in its history.
    """
    cursor.execute("""
        SELECT
            t.THREAD_ID,
            COALESCE(MAX(es.EVENT_ID), 0) AS last_event_id
        FROM performance_schema.threads AS t
        LEFT JOIN performance_schema.events_statements_history AS es
            ON es.THREAD_ID = t.THREAD_ID
        WHERE t.PROCESSLIST_ID = CONNECTION_ID()
        GROUP BY t.THREAD_ID
    """)

    row = cursor.fetchone()

    if not row:
        return None, None

    return row["THREAD_ID"], row["last_event_id"]


def get_statement_duration_ms(cursor, thread_id, baseline_event_id):
    """
    Retrieve the database-side TIMER_WAIT for the statement event
    produced after the baseline.

    Returns None when a reliable event cannot be found.
    """
    if thread_id is None or baseline_event_id is None:
        return None

    cursor.execute("""
        SELECT TIMER_WAIT
        FROM performance_schema.events_statements_history
        WHERE THREAD_ID = %s
          AND EVENT_ID > %s
          AND TIMER_WAIT IS NOT NULL
        ORDER BY EVENT_ID DESC
        LIMIT 1
    """, (thread_id, baseline_event_id))

    row = cursor.fetchone()

    if not row or row["TIMER_WAIT"] is None:
        return None

    # TIMER_WAIT is in picoseconds. Divide by 1e9 to get milliseconds.
    return round(float(row["TIMER_WAIT"]) / 1_000_000_000, 3)


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
        Execute one SQL statement and record:
        - duration_ms: MySQL-side statement execution time
        - total_elapsed_ms: Python-side end-to-end elapsed time
        """
        start_time = time.perf_counter()

        status = "UNAVAILABLE"
        db_duration_ms = None
        total_elapsed_ms = None
        results = None
        rows_affected = 0
        error_msg = None

        try:
            with DatabasePool.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                if schema_name and schema_name != "default":
                    # Schema names are identifiers, not SQL values.
                    # Validate them before interpolation.
                    if not schema_name.replace("_", "").isalnum():
                        raise ValueError("Invalid schema name")

                    cursor.execute(f"USE `{schema_name}`")

                # Failure to read Performance Schema must not prevent
                # the actual SQL query from running.
                thread_id = None
                baseline_event_id = None

                try:
                    thread_id, baseline_event_id = (
                        get_statement_baseline(cursor)
                    )
                except Error as timing_error:
                    logger.warning(
                        "Could not establish Performance Schema baseline: %s",
                        timing_error
                    )

                # Execute the actual target statement.
                cursor.execute(sql_query)

                if cursor.description:
                    # Consume the result set before reusing the cursor.
                    results = cursor.fetchall()
                    rows_affected = len(results)

                    try:
                        db_duration_ms = get_statement_duration_ms(
                            cursor,
                            thread_id,
                            baseline_event_id
                        )
                    except Error as timing_error:
                        logger.warning(
                            "Could not retrieve database timing: %s",
                            timing_error
                        )
                else:
                    # Capture the statement event before COMMIT can
                    # become the latest statement event.
                    try:
                        db_duration_ms = get_statement_duration_ms(
                            cursor,
                            thread_id,
                            baseline_event_id
                        )
                    except Error as timing_error:
                        logger.warning(
                            "Could not retrieve database timing: %s",
                            timing_error
                        )

                    conn.commit()
                    rows_affected = cursor.rowcount

                cursor.close()

        except Error as err:
            logger.error("Database query error: %s", err)
            error_msg = str(err)
            status = "ERROR"
            results = [{"error": error_msg}]

        except Exception as ex:
            logger.exception("Unexpected query execution error")
            error_msg = str(ex)
            status = "ERROR"
            results = [{"error": error_msg}]

        finally:
            total_elapsed_ms = round(
                (time.perf_counter() - start_time) * 1000, 3
            )

        # Classify using the database-side duration, not Python elapsed time.
        if status != "ERROR":
            if db_duration_ms is None:
                status = "UNAVAILABLE"
            elif db_duration_ms > settings.SLOW_QUERY_THRESHOLD_MS:
                status = "SLOW"
            else:
                status = "FAST"

        record = QueryInterceptorService._save_query_run(
            sql_text=sql_query,
            schema_name=schema_name,
            duration_ms=db_duration_ms,
            total_elapsed_ms=total_elapsed_ms,
            status=status
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
        unavailable_count = 0
        total_dur_ms = 0.0
        durations = []
        total_elapsed_dur_ms = 0.0
        total_elapsed_durations = []

        for index, stmt in enumerate(statements, start=1):
            stmt_clean = stmt.strip()
            if not stmt_clean:
                continue

            record, rows, results, error = QueryInterceptorService.execute_and_intercept(
                sql_query=stmt_clean,
                schema_name=schema_name
            )

            dur = record.get("duration_ms")
            total_elapsed = record.get("total_elapsed_ms")

            if dur is not None:
                total_dur_ms += dur
                durations.append(dur)

            if total_elapsed is not None:
                total_elapsed_dur_ms += total_elapsed
                total_elapsed_durations.append(total_elapsed)

            
            st_status = record.get("status", "UNAVAILABLE")

            if error:
                st_status = "ERROR"
                error_count += 1
            elif dur is None:
                st_status = "UNAVAILABLE"
                unavailable_count += 1
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
                "total_elapsed_ms" : total_elapsed,
                "status": st_status,
                "rows_affected": rows,
                "error": error,
                "timestamp": record.get("timestamp", datetime.now()),
                "queryID": record.get("queryID"),
                "rank": 0
            }
            executed_records.append(stmt_result)

        # Multi-criteria ranking
        rankable_records = [
            r for r in executed_records
            if r["duration_ms"] is not None
        ]

        unavailable_records = [
            r for r in executed_records
            if r["duration_ms"] is None
        ]

        ranked_records = SQLParserService.rank_statements(
            rankable_records, rank_by=rank_by
        )

        for record in unavailable_records:
            record["rank"] = 0

        ranked_records.extend(unavailable_records)

        total_stmts = len(executed_records)

        avg_dur = (
            round(total_dur_ms / len(durations), 3)
            if durations else 0.0
        )

        max_dur = max(durations) if durations else 0.0
        min_dur = min(durations) if durations else 0.0

        slow_pct = (
            round((slow_count / total_stmts * 100), 2)
            if total_stmts > 0 else 0.0
        )

        avg_total_elapsed = (
            round(total_elapsed_dur_ms / len(total_elapsed_durations), 3)
            if total_elapsed_durations else 0.0
        )

        summary = {
            "total_statements": total_stmts,
            "successful_statements": total_stmts - error_count,
            "failed_statements": error_count,
            "slow_statements": slow_count,
            "fast_statements": fast_count,
            "unavailable_statements": unavailable_count,
            "total_duration_ms": round(total_dur_ms, 3),
            "avg_duration_ms": avg_dur,
            "max_duration_ms": round(max_dur, 3),
            "min_duration_ms": round(min_dur, 3),
            "slow_percentage": slow_pct,
            "total_elapsed_ms": round(total_elapsed_dur_ms, 3),
            "avg_total_elapsed_ms": avg_total_elapsed,
        }

        return summary, ranked_records

    
    @staticmethod
    def _save_query_run(
        sql_text: str,
        schema_name: str,
        duration_ms: Optional[float],
        total_elapsed_ms: Optional[float],
        status: str
    ) -> dict:
        now = datetime.now()
        record_id = -1

        try:
            with DatabasePool.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    INSERT INTO QueryRuns (
                        sql_text,
                        current_schema,
                        duration_ms,
                        total_elapsed_ms,
                        status,
                        timestamp
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """

                cursor.execute(
                    query,
                    (
                        sql_text,
                        schema_name,
                        duration_ms,
                        total_elapsed_ms,
                        status,
                        now
                    )
                )

                conn.commit()
                record_id = cursor.lastrowid
                cursor.close()

        except Exception as e:
            logger.exception("Failed to record query execution log: %s", e)

        return {
            "queryID": record_id,
            "sql_text": sql_text,
            "current_schema": schema_name,
            "duration_ms": duration_ms,
            "total_elapsed_ms": total_elapsed_ms,
            "status": status,
            "timestamp": now
        }