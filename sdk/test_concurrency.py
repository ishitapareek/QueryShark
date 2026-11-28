
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import mysql.connector

from queryshark import QuerySharkClient, instrument_connection
from queryshark.performance import PerformanceSchemaMonitor


WORKERS = 10
QUERIES_PER_WORKER = 1000
EXPECTED_QUERIES = WORKERS * (QUERIES_PER_WORKER + 1)

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

client = QuerySharkClient(
    agent_url=AGENT_URL,
    queue_size=200000,
    buffer_size=100000,
    batch_size=100,
    request_timeout=10
)

captured = []
accepted = []
rejected = []
slow_records = []

lock = threading.Lock()


def capture_telemetry(record):
    result = client.send_telemetry(record)

    with lock:
        captured.append(record)

        if result:
            accepted.append(record)
        else:
            rejected.append(record)

        if record["status"] == "SLOW":
            slow_records.append(record)

    return result


def run_worker(worker_id):
    app_connection = mysql.connector.connect(**DB_CONFIG)
    monitor_connection = mysql.connector.connect(**DB_CONFIG)

    monitor = PerformanceSchemaMonitor(
        monitor_connection,
        app_connection.connection_id
    )

    connection = instrument_connection(
        app_connection,
        on_query=capture_telemetry,
        performance_monitor=monitor,
        slow_threshold_ms=100.0
    )

    cursor = connection.cursor()

    completed = 0

    try:
        for _ in range(QUERIES_PER_WORKER):
            cursor.execute("SELECT 1")
            cursor.fetchone()
            completed += 1

        # One slow-query test per worker
        cursor.execute("SELECT SLEEP(0.15)")
        cursor.fetchone()

        return completed + 1

    finally:
        cursor.close()
        connection.close()
        monitor_connection.close()


if __name__ == "__main__":
    print("=" * 55)
    print("QUERYSHARK CONCURRENT CONNECTION TEST")
    print(f"Workers: {WORKERS}")
    print(f"Queries per worker: {QUERIES_PER_WORKER:,} + 1 slow query")
    print("=" * 55)

    start = time.perf_counter()

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            results = list(
                executor.map(run_worker, range(WORKERS))
            )

        execution_time = time.perf_counter() - start

        print(f"\nCompleted queries: {sum(results):,}")
        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Throughput: {sum(results) / execution_time:.2f} queries/sec")

    except Exception:
        client.close(timeout=600)
        raise

    print("\nWaiting for telemetry delivery...")
    client.close(timeout=600)

    pending = client.pending_count()
    buffered = client.buffered_count()

    print(f"\nTelemetry generated: {len(captured):,}")
    print(f"Telemetry accepted: {len(accepted):,}")
    print(f"Telemetry rejected: {len(rejected):,}")
    print(f"Slow queries detected: {len(slow_records):,}")
    print(f"SQLite pending: {pending:,}")
    print(f"Memory buffered: {buffered:,}")

    passed = (
        len(captured) == EXPECTED_QUERIES
        and len(accepted) == EXPECTED_QUERIES
        and len(rejected) == 0
        and len(slow_records) == WORKERS
        and pending == 0
        and buffered == 0
    )

    print("\n" + "=" * 55)
    print("CONCURRENT TEST:", "PASSED" if passed else "INCOMPLETE")
    print("=" * 55)