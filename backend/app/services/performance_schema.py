import logging
from typing import List, Dict, Any
from app.db.connection import DatabasePool

logger = logging.getLogger(__name__)

class PerformanceSchemaService:
    """
    Service for extracting engine-level performance diagnostics
    directly from MySQL's internal performance_schema tables.
    """

    @staticmethod
    def is_enabled() -> bool:
        """Checks if Performance Schema is enabled on the connected MySQL server."""
        try:
            with DatabasePool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SHOW VARIABLES LIKE 'performance_schema';")
                row = cursor.fetchone()
                cursor.close()
                return bool(row and row[1].upper() == "ON")
        except Exception as e:
            logger.warning(f"Failed to check performance_schema status: {e}")
            return False

    @staticmethod
    def get_top_digest_queries(limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves top resource-intensive query digests directly from MySQL performance_schema.
        Converts picosecond timer waits into milliseconds.
        """
        query = """
        SELECT 
            SCHEMA_NAME as schema_name,
            DIGEST_TEXT as query_template,
            COUNT_STAR as execution_count,
            ROUND(SUM_TIMER_WAIT / 1000000000, 2) as total_latency_ms,
            ROUND(AVG_TIMER_WAIT / 1000000000, 2) as avg_latency_ms,
            ROUND(MAX_TIMER_WAIT / 1000000000, 2) as max_latency_ms,
            SUM_ROWS_EXAMINED as rows_examined,
            SUM_ROWS_SENT as rows_sent
        FROM performance_schema.events_statements_summary_by_digest
        WHERE DIGEST_TEXT IS NOT NULL 
          AND SCHEMA_NAME NOT IN ('performance_schema', 'sys', 'information_schema')
        ORDER BY SUM_TIMER_WAIT DESC
        LIMIT %s;
        """
        records = []
        try:
            with DatabasePool.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (limit,))
                records = cursor.fetchall()
                cursor.close()
        except Exception as e:
            logger.warning(f"Could not query performance_schema digests: {e}")

        return records
