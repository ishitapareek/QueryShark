
import logging
import threading

logger = logging.getLogger(__name__)


class PerformanceSchemaMonitor:
    """
    Retrieves server-side SQL execution time from MySQL Performance Schema.

    Each monitor instance belongs to one application connection.
    Reuses a monitoring cursor to reduce per-query overhead.
    """

    def __init__(self, monitoring_connection, application_connection_id):
        self.monitoring_connection = monitoring_connection
        self.application_connection_id = application_connection_id
        self.thread_id = None

        self._cursor = monitoring_connection.cursor()
        self._lock = threading.RLock()

    def get_thread_id(self):
        with self._lock:
            if self.thread_id is not None:
                return self.thread_id

            try:
                self._cursor.execute("""
                    SELECT THREAD_ID
                    FROM performance_schema.threads
                    WHERE PROCESSLIST_ID = %s
                """, (self.application_connection_id,))

                result = self._cursor.fetchone()

                if result:
                    self.thread_id = result[0]

                return self.thread_id

            except Exception:
                logger.exception("Could not retrieve MySQL thread ID.")
                return None

    def get_statement_duration_ms(self):
        """
        Retrieves the latest completed statement duration.

        TIMER_WAIT is in picoseconds.
        Conversion to milliseconds: divide by 1,000,000,000.
        """

        with self._lock:
            try:
                if self.thread_id is None:
                    self.get_thread_id()

                if self.thread_id is None:
                    return None

                self._cursor.execute("""
                    SELECT TIMER_WAIT
                    FROM performance_schema.events_statements_history
                    WHERE THREAD_ID = %s
                      AND TIMER_WAIT IS NOT NULL
                    ORDER BY EVENT_ID DESC
                    LIMIT 1
                """, (self.thread_id,))

                result = self._cursor.fetchone()

                if not result or result[0] is None:
                    return None

                return float(result[0]) / 1_000_000_000

            except Exception:
                logger.exception(
                    "Could not retrieve statement execution time."
                )
                return None

    def close(self):
        with self._lock:
            if self._cursor is not None:
                self._cursor.close()
                self._cursor = None
