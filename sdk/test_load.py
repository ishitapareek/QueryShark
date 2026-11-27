
import time
from datetime import datetime, timezone

from queryshark.client import QuerySharkClient

TOTAL_RECORDS = 100000
BATCH_SIZE = 100
WAIT_TIMEOUT = 120

client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000",
    batch_size=BATCH_SIZE,
    request_timeout=10
)

# Generate records in memory first.
records = []

for i in range(TOTAL_RECORDS):
    records.append({
        "sql_text": f"SELECT {i}",
        "current_schema": "queryshark_load_test",
        "duration_ms": 10.5 + (i % 50),
        "total_elapsed_ms": 11.2 + (i % 50),
        "status": "FAST",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# Measure bulk enqueue time.
start_time = time.perf_counter()

accepted = client.send_telemetry_batch(records)

enqueue_time = time.perf_counter() - start_time

print(f"\nRecords submitted: {TOTAL_RECORDS}")
print(f"Records accepted: {accepted}")
print(f"Records pending: {client.pending_count()}")
print(f"Enqueue time: {enqueue_time:.4f} seconds")

# Wait for delivery.
delivery_start = time.perf_counter()
deadline = delivery_start + WAIT_TIMEOUT

while client.pending_count() > 0 and time.perf_counter() < deadline:
    time.sleep(0.2)

delivery_time = time.perf_counter() - delivery_start
remaining = client.pending_count()

client.close()

total_time = enqueue_time + delivery_time

print("\n========== LOAD TEST RESULTS ==========")
print(f"Records submitted: {TOTAL_RECORDS}")
print(f"Records accepted: {accepted}")
print(f"Records remaining: {remaining}")
print(f"Enqueue time: {enqueue_time:.4f} seconds")
print(f"Delivery wait time: {delivery_time:.2f} seconds")
print(f"Total time: {total_time:.2f} seconds")
print(f"Throughput: {accepted / total_time:.2f} records/second")

if accepted == TOTAL_RECORDS and remaining == 0:
    print("\nRESULT: SUCCESS")
else:
    print("\nRESULT: INCOMPLETE - CHECK LOGS AND SQLITE QUEUE")
