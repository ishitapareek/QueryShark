
import logging
import time
from datetime import datetime, timezone

from .performance import PerformanceSchemaMonitor

logger = logging.getLogger(__name__)


class QuerySharkCursor:

    def __init__(
        self,
        cursor,
        on_query=None,
        performance_monitor=None,
        slow_threshold_ms=100.0
    ):
        self._cursor = cursor
        self._on_query = on_query
        self._monitor = performance_monitor
        self._threshold = slow_threshold_ms

    def execute(self, operation, params=None, *args, **kwargs):
        baseline = None

        if self._monitor:
            baseline = self._monitor.get_baseline()

        start_time = time.perf_counter()
        status = "UNAVAILABLE"

        try:
            if params is None:
                result = self._cursor.execute(
                    operation, *args, **kwargs
                )
            else:
                result = self._cursor.execute(
                    operation, params, *args, **kwargs
                )

            return result

        except Exception:
            status = "ERROR"
            raise

        finally:
            elapsed_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self._capture(
                operation,
                elapsed_ms,
                status,
                baseline
            )

    def executemany(self, operation, seq_params):
        baseline = None

        if self._monitor:
            baseline = self._monitor.get_baseline()

        start_time = time.perf_counter()
        status = "UNAVAILABLE"

        try:
            result = self._cursor.executemany(
                operation, seq_params
            )
            return result

        except Exception:
            status = "ERROR"
            raise

        finally:
            elapsed_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self._capture(
                operation,
                elapsed_ms,
                status,
                baseline
            )

    def _capture(
        self,
        operation,
        elapsed_ms,
        status,
        baseline
    ):
        if self._on_query is None:
            return

        duration_ms = None

        if status != "ERROR" and self._monitor:
            duration_ms = (
                self._monitor.get_statement_duration_ms(
                    baseline
                )
            )

        if status != "ERROR":
            if duration_ms is None:
                status = "UNAVAILABLE"
            elif duration_ms > self._threshold:
                status = "SLOW"
            else:
                status = "FAST"

        record = {
            "sql_text": str(operation),
            "duration_ms": duration_ms,
            "total_elapsed_ms": elapsed_ms,
            "status": status,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }

        try:
            self._on_query(record)

        except Exception:
            logger.exception(
                "QueryShark telemetry capture failed."
            )

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._cursor.__exit__(
            exc_type, exc_value, traceback
        )


class QuerySharkConnection:

    def __init__(
        self,
        connection,
        on_query=None,
        performance_monitor=None,
        slow_threshold_ms=100.0
    ):
        self._connection = connection
        self._on_query = on_query
        self._monitor = performance_monitor
        self._threshold = slow_threshold_ms

    def cursor(self, *args, **kwargs):
        original_cursor = self._connection.cursor(
            *args, **kwargs
        )

        return QuerySharkCursor(
            original_cursor,
            self._on_query,
            self._monitor,
            self._threshold
        )

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._connection.__exit__(
            exc_type, exc_value, traceback
        )


def instrument_connection(
    connection,
    on_query=None,
    performance_monitor=None,
    slow_threshold_ms=100.0
):
    return QuerySharkConnection(
        connection,
        on_query,
        performance_monitor,
        slow_threshold_ms
    )
