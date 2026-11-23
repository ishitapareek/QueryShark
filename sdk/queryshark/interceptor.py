
import logging
import time
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class QuerySharkCursor:
    """
    Wrapper around the original MySQL cursor.

    Executes queries normally while capturing query information.
    """

    def __init__(self, cursor, on_query=None):
        self._cursor = cursor
        self._on_query = on_query

    def execute(self, operation, params=None, *args, **kwargs):
        start_time = time.perf_counter()
        status = "UNAVAILABLE"

        try:
            if params is None:
                return self._cursor.execute(
                    operation, *args, **kwargs
                )

            return self._cursor.execute(
                operation, params, *args, **kwargs
            )

        except Exception:
            status = "ERROR"
            raise

        finally:
            elapsed_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self._capture(
                operation=operation,
                elapsed_ms=elapsed_ms,
                status=status
            )

    def executemany(self, operation, seq_params):
        start_time = time.perf_counter()
        status = "UNAVAILABLE"

        try:
            return self._cursor.executemany(
                operation, seq_params
            )

        except Exception:
            status = "ERROR"
            raise

        finally:
            elapsed_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self._capture(
                operation=operation,
                elapsed_ms=elapsed_ms,
                status=status
            )

    def _capture(self, operation, elapsed_ms, status):
        if self._on_query is None:
            return

        record = {
            "sql_text": str(operation),
            "duration_ms": None,
            "total_elapsed_ms": elapsed_ms,
            "status": status,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }

        try:
            self._on_query(record)
        except Exception:
            # Monitoring failures must not break the application.
            logger.exception(
                "QueryShark telemetry capture failed"
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
    """
    Wrapper around a MySQL connection.
    """

    def __init__(self, connection, on_query=None):
        self._connection = connection
        self._on_query = on_query

    def cursor(self, *args, **kwargs):
        original_cursor = self._connection.cursor(
            *args, **kwargs
        )

        return QuerySharkCursor(
            original_cursor,
            self._on_query
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


def instrument_connection(connection, on_query=None):
    """
    Instrument an existing mysql.connector connection.

    Returns a wrapped connection.
    """

    return QuerySharkConnection(
        connection,
        on_query
    )
