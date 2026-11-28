
import os
import time
import mysql.connector

from queryshark import QuerySharkClient, instrument_connection
from queryshark.performance import PerformanceSchemaMonitor


TOTAL_QUERIES = 1000

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "admin"),
    "database": os.getenv("MYSQL_DATABASE", "queryshark")
}

AGENT_URL = os.getenv(
    "QUERYSHARK_AGENT_URL",
    "http://127.0.0.1:8000"
)


def run_test(label, monitor_enabled, telemetry_enabled):

    print(f"\n--- {label} ---")

    app_connection = mysql.connector.connect(**DB_CONFIG)

    monitor_connection = None
    client = None

    try:
        monitor = None

        if monitor_enabled:
            monitor_connection = mysql.connector.connect(**DB_CONFIG)

            monitor = PerformanceSchemaMonitor(
                monitor_connection,
                app_connection.connection_id
            )

        if telemetry_enabled:
            client = QuerySharkClient(
                agent_url=AGENT_URL,
                queue_size=100000,
                batch_size=100,
                request_timeout=10
            )
            callback = client.send_telemetry
        else:
            callback = lambda record: None

        connection = instrument_connection(
            app_connection,
            on_query=callback,
            performance_monitor=monitor,
            slow_threshold_ms=100.0
        )

        cursor = connection.cursor()

        start = time.perf_counter()

        for i in range(TOTAL_QUERIES):
            cursor.execute("SELECT 1")
            cursor.fetchone()

            if (i + 1) % 250 == 0:
                print(f"Executed: {i + 1:,}")

        elapsed = time.perf_counter() - start

        cursor.close()

        print(f"Execution + capture: {elapsed:.3f} seconds")
        print(f"Throughput: {TOTAL_QUERIES / elapsed:.2f} queries/sec")

        if client:
            print("Waiting for telemetry delivery...")

            deadline = time.perf_counter() + 600

            while client.pending_count() > 0:
                if time.perf_counter() >= deadline:
                    break
                time.sleep(1)

            print("Pending records:", client.pending_count())

        return elapsed

    finally:
        if client:
            client.close()

        if monitor_connection:
            monitor_connection.close()

        app_connection.close()


if __name__ == "__main__":

    print("=" * 50)
    print("QUERYSHARK OVERHEAD DIAGNOSTICS")
    print(f"Queries per test: {TOTAL_QUERIES:,}")
    print("=" * 50)

    # B: SQLite persistence and telemetry capture, without monitoring.
    sqlite_time = run_test(
        "TEST B: PERFORMANCE SCHEMA OFF, TELEMETRY ON",
        monitor_enabled=False,
        telemetry_enabled=True
    )

    # C: Performance Schema monitoring, without SQLite persistence.
    monitor_time = run_test(
        "TEST C: PERFORMANCE SCHEMA ON, TELEMETRY OFF",
        monitor_enabled=True,
        telemetry_enabled=False
    )

    print("\n" + "=" * 50)
    print("DIAGNOSTIC RESULTS")
    print("=" * 50)
    print(f"SQLite + capture only: {sqlite_time:.3f} seconds")
    print(f"Performance monitoring only: {monitor_time:.3f} seconds")
    print("=" * 50)
