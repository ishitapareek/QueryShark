
import time
from datetime import datetime, timezone

from queryshark.client import QuerySharkClient

TOTAL_RECORDS = 100000
WAIT_TIMEOUT = 300

client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000",
    batch_size=100,
    request_timeout=10
)

records = []

for i in range(TOTAL_RECORDS):
    records.append({
        "sql_text": f"SELECT {i}",
        "current_schema": "queryshark_recovery_100k",
        "duration_ms": 15.5,
        "total_elapsed_ms": 16.2,
        "status": "FAST",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

print("Submitting 100,000 records...")

accepted = client.send_telemetry_batch(records)

print(f"Records accepted: {accepted}")
print(f"Records pending: {client.pending_count()}")

input(
    "\nBackend is OFFLINE. Start FastAPI in another terminal, "
    "then press ENTER here to monitor recovery..."
)

start_time = time.perf_counter()
deadline = start_time + WAIT_TIMEOUT

while client.pending_count() > 0 and time.perf_counter() < deadline:
    time.sleep(1)

remaining = client.pending_count()
elapsed = time.perf_counter() - start_time

client.close()

print("\n========== 100K FAILURE RECOVERY RESULTS ==========")
print(f"Records accepted: {accepted}")
print(f"Records remaining: {remaining}")
print(f"Recovery time: {elapsed:.2f} seconds")

if accepted == TOTAL_RECORDS and remaining == 0:
    print("RESULT: SUCCESS - All 100K records recovered.")
else:
    print("RESULT: INCOMPLETE - Check SQLite queue and logs.")
