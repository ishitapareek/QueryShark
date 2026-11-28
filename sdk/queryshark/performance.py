
import logging

logger = logging.getLogger(__name__)


class PerformanceSchemaMonitor:
    """
    Retrieves server-side SQL execution time from MySQL Performance Schema.

    Each monitor instance should correspond to one application connection.
    """

    def __init__(self, monitoring_connection, application_connection_id):
        self.monitoring_connection = monitoring_connection
        self.application_connection_id = application_connection_id
        self.thread_id = None

    def get_thread_id(self):
        cursor = self.monitoring_connection.cursor()

        try:
            cursor.execute("""
                SELECT THREAD_ID
                FROM performance_schema.threads
                WHERE PROCESSLIST_ID = %s
            """, (self.application_connection_id,))

            result = cursor.fetchone()

            if result:
                self.thread_id = result[0]

            return self.thread_id

        finally:
            cursor.close()

    def get_statement_duration_ms(self):
        """
        Retrieve the most recent completed statement duration
        for the monitored application connection.

        TIMER_WAIT is measured in picoseconds.
        Conversion to milliseconds: divide by 1,000,000,000.
        """

        try:
            if self.thread_id is None:
                self.get_thread_id()

            if self.thread_id is None:
                return None

            cursor = self.monitoring_connection.cursor()

            try:
                cursor.execute("""
                    SELECT TIMER_WAIT
                    FROM performance_schema.events_statements_history
                    WHERE THREAD_ID = %s
                      AND TIMER_WAIT IS NOT NULL
                    ORDER BY EVENT_ID DESC
                    LIMIT 1
                """, (self.thread_id,))

                result = cursor.fetchone()

                if not result or result[0] is None:
                    return None

                return float(result[0]) / 1_000_000_000

            finally:
                cursor.close()

        except Exception:
            logger.exception(
                "Could not retrieve statement execution time."
            )
            return None
