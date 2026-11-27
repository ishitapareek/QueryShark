
import os
import time
import mysql.connector

from queryshark import QuerySharkClient, instrument_connection
from queryshark.performance import PerformanceSchemaMonitor


# Start with 1,000 queries. Increase to 100,000 after the pilot passes.
TOTAL_QUERIES = int(
    os.getenv("QUERYSHARK_BENCHMARK_QUERIES", "1000")
)

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


def run_without_queryshark():
    print("\n--- TEST A: WITHOUT QUERYSHARK ---")

    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    start = time.perf_counter()

    for i in range(TOTAL_QUERIES):
        cursor.execute("SELECT 1")
        cursor.fetchone()

        if (i + 1) % 10000 == 0:
            print(f"Executed: {i + 1:,}")

    elapsed = time.perf_counter() - start

    cursor.close()
    connection.close()

    print(f"Queries: {TOTAL_QUERIES:,}")
    print(f"Execution time: {elapsed:.3f} seconds")
    print(f"Throughput: {TOTAL_QUERIES / elapsed:.2f} queries/sec")

    return elapsed


def run_with_queryshark():
    print("\n--- TEST B: WITH QUERYSHARK ---")

    app_connection = mysql.connector.connect(**DB_CONFIG)

    monitor_connection = mysql.connector.connect(**DB_CONFIG)

    monitor = PerformanceSchemaMonitor(
        monitor_connection,
        app_connection.connection_id
    )

    client = QuerySharkClient(
        agent_url=AGENT_URL,
        queue_size=max(TOTAL_QUERIES * 2, 100000),
        batch_size=100,
        request_timeout=10
    )

    connection = instrument_connection(
        app_connection,
        on_query=client.send_telemetry,
        performance_monitor=monitor,
        slow_threshold_ms=100.0
    )

    cursor = connection.cursor()

    start = time.perf_counter()

    for i in range(TOTAL_QUERIES):
        cursor.execute("SELECT 1")
        cursor.fetchone()

        if (i + 1) % 10000 == 0:
            print(f"Executed: {i + 1:,}")

    execution_elapsed = time.perf_counter() - start

    cursor.close()

    print(f"Queries: {TOTAL_QUERIES:,}")
    print(f"Execution + capture time: {execution_elapsed:.3f} seconds")
    print(
        f"Throughput: "
        f"{TOTAL_QUERIES / execution_elapsed:.2f} queries/sec"
    )

    print("\nWaiting for telemetry delivery...")

    delivery_start = time.perf_counter()
    deadline = time.perf_counter() + 600

    while client.pending_count() > 0:
        if time.perf_counter() >= deadline:
            break
        time.sleep(1)

    delivery_elapsed = time.perf_counter() - delivery_start
    remaining = client.pending_count()

    print(f"Delivery wait: {delivery_elapsed:.2f} seconds")
    print(f"Records remaining in SQLite: {remaining:,}")

    client.close()
    monitor_connection.close()
    app_connection.close()

    return execution_elapsed, remaining


if __name__ == "__main__":

    print("=" * 50)
    print("QUERYSHARK REAL SQL BENCHMARK")
    print(f"Total queries per test: {TOTAL_QUERIES:,}")
    print("=" * 50)

    baseline = run_without_queryshark()

    monitored, pending = run_with_queryshark()

    overhead = (
        (monitored - baseline) / baseline
    ) * 100

    print("\n" + "=" * 50)
    print("BENCHMARK RESULTS")
    print("=" * 50)

    print(f"Without QueryShark: {baseline:.3f} seconds")
    print(f"With QueryShark:    {monitored:.3f} seconds")
    print(f"Additional time:    {monitored - baseline:.3f} seconds")
    print(f"Relative overhead:  {overhead:.2f}%")
    print(f"Pending telemetry:  {pending:,}")

    print("=" * 50)

    if pending == 0:
        print("TELEMETRY DELIVERY: PASSED")
    else:
        print("TELEMETRY DELIVERY: INCOMPLETE")
