
import logging

logger = logging.getLogger(__name__)


class PerformanceSchemaMonitor:
    """
    Retrieves server-side execution time for a query
    executed by an external MySQL connection.
    """

    def __init__(self, monitoring_connection, application_connection_id):
        self.monitoring_connection = monitoring_connection
        self.application_connection_id = application_connection_id
        self.thread_id = None

    def get_thread_id(self):
        """Find the MySQL thread belonging to the application connection."""

        cursor = self.monitoring_connection.cursor()

        try:
            cursor.execute(
                """
                SELECT THREAD_ID
                FROM performance_schema.threads
                WHERE PROCESSLIST_ID = %s
                """,
                (self.application_connection_id,)
            )

            result = cursor.fetchone()

            if result:
                self.thread_id = result[0]

            return self.thread_id

        finally:
            cursor.close()

    def get_latest_event_id(self):
        """Get the latest recorded statement event for this thread."""

        if self.thread_id is None:
            return None

        cursor = self.monitoring_connection.cursor()

        try:
            cursor.execute(
                """
                SELECT COALESCE(MAX(EVENT_ID), 0)
                FROM performance_schema.events_statements_history
                WHERE THREAD_ID = %s
                """,
                (self.thread_id,)
            )

            result = cursor.fetchone()
            return result[0] if result else 0

        finally:
            cursor.close()

    def get_baseline(self):
        """Capture the event ID before application query execution."""

        try:
            if self.thread_id is None:
                self.get_thread_id()

            if self.thread_id is None:
                return None

            return self.get_latest_event_id()

        except Exception:
            logger.exception(
                "Could not capture Performance Schema baseline."
            )
            return None

    def get_statement_duration_ms(self, baseline_event_id):
        """
        Retrieve the execution time of the statement recorded
        after the supplied baseline event ID.

        TIMER_WAIT is measured in picoseconds.
        """

        if self.thread_id is None or baseline_event_id is None:
            return None

        cursor = self.monitoring_connection.cursor()

        try:
            cursor.execute(
                """
                SELECT TIMER_WAIT
                FROM performance_schema.events_statements_history
                WHERE THREAD_ID = %s
                  AND EVENT_ID > %s
                  AND TIMER_WAIT IS NOT NULL
                ORDER BY EVENT_ID DESC
                LIMIT 1
                """,
                (self.thread_id, baseline_event_id)
            )

            result = cursor.fetchone()

            if not result or result[0] is None:
                return None

            # Convert picoseconds to milliseconds.
            return float(result[0]) / 1_000_000_000

        except Exception:
            logger.exception(
                "Could not retrieve statement execution time."
            )
            return None

        finally:
            cursor.close()
