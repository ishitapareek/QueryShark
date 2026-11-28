
import os
import time
import mysql.connector

from queryshark import QuerySharkClient, instrument_connection
from queryshark.performance import PerformanceSchemaMonitor


TOTAL_QUERIES = int(os.getenv("QUERYSHARK_BENCHMARK_QUERIES", "1000"))

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

    for _ in range(TOTAL_QUERIES):
        cursor.execute("SELECT 1")
        cursor.fetchone()

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
        queue_size=max(TOTAL_QUERIES * 2, 200000),
        buffer_size=max(TOTAL_QUERIES * 2, 100000),
        batch_size=100,
        request_timeout=10
    )

    captured_records = []
    accepted_records = []
    rejected_records = []

    def capture_telemetry(record):
        captured_records.append(record)

        accepted = client.send_telemetry(record)

        if accepted:
            accepted_records.append(record)
        else:
            rejected_records.append(record)

        return accepted 

    connection = instrument_connection(
        app_connection,
        on_query=capture_telemetry,
        performance_monitor=monitor,
        slow_threshold_ms=100.0
    )

    cursor = connection.cursor()

    # Benchmark: 1,000 actual SQL queries
    start = time.perf_counter()

    for _ in range(TOTAL_QUERIES):
        cursor.execute("SELECT 1")
        cursor.fetchone()

    execution_elapsed = time.perf_counter() - start

    print(f"Queries: {TOTAL_QUERIES:,}")
    print(f"Execution time: {execution_elapsed:.3f} seconds")
    print(f"Throughput: {TOTAL_QUERIES / execution_elapsed:.2f} queries/sec")

    # Separate correctness test: slow-query detection
    print("\n--- SLOW QUERY CORRECTNESS TEST ---")

    cursor.execute("SELECT SLEEP(0.15)")
    cursor.fetchone()

    sleep_record = next(
        (r for r in reversed(captured_records)
         if "SLEEP" in r["sql_text"].upper()),
        None
    )

    if sleep_record:
        print(f"Duration: {sleep_record['duration_ms']} ms")
        print(f"Status: {sleep_record['status']}")
        print(
            "Slow query detection:",
            "PASSED" if (
                sleep_record["duration_ms"] is not None
                and sleep_record["duration_ms"] > 100
                and sleep_record["status"] == "SLOW"
            ) else "FAILED"
        )
    else:
        print("Slow query detection: FAILED - no telemetry record found")

    cursor.close()

    print(f"\nTelemetry records generated: {len(captured_records):,}")
    print(f"Telemetry records accepted: {len(accepted_records):,}")
    print(f"Telemetry records rejected: {len(rejected_records):,}")

    # Wait for telemetry delivery
    print("Waiting for telemetry delivery...")

    delivery_start = time.perf_counter()
    deadline = time.perf_counter() + 600

    while client.pending_count() > 0 or client.buffered_count() > 0:
        if time.perf_counter() >= deadline:
            break
        time.sleep(1)

    print(
        f"Delivery wait: "
        f"{time.perf_counter() - delivery_start:.2f} seconds"
    )

    client.close()

    remaining = client.pending_count()
    buffered = client.buffered_count()

    print(f"Records remaining in SQLite: {remaining:,}")
    print(f"Records remaining in memory: {buffered:,}")

    monitor_connection.close()
    app_connection.close()

    return (
        execution_elapsed,
        remaining,
        buffered,
        len(captured_records),
        len(accepted_records),
        len(rejected_records)
    )


if __name__ == "__main__":

    print("=" * 55)
    print("QUERYSHARK REAL SQL BENCHMARK")
    print(f"Queries per test: {TOTAL_QUERIES:,}")
    print("=" * 55)

    baseline = run_without_queryshark()

    (
        monitored,
        pending,
        buffered,
        generated,
        accepted,
        rejected
    ) = run_with_queryshark()

    overhead = ((monitored - baseline) / baseline) * 100

    print("\n" + "=" * 55)
    print("BENCHMARK RESULTS")
    print("=" * 55)

    print(f"Without QueryShark: {baseline:.3f} seconds")
    print(f"With QueryShark:    {monitored:.3f} seconds")
    print(f"Additional time:    {monitored - baseline:.3f} seconds")
    print(f"Relative overhead:  {overhead:.2f}%")
    print(f"Telemetry generated: {generated:,}")
    print(f"Pending telemetry:   {pending:,}")
    print(f"Buffered telemetry:  {buffered:,}")

    print("=" * 55)

    print(f"\nTelemetry records generated: {generated:,}")
    print(f"Telemetry records accepted: {accepted:,}")
    print(f"Telemetry records rejected: {rejected:,}")

    if (
        pending == 0
        and buffered == 0
        and accepted == TOTAL_QUERIES + 1
        and rejected == 0
    ):
        print("TELEMETRY DELIVERY: PASSED")
    else:
        print("TELEMETRY DELIVERY: INCOMPLETE")
