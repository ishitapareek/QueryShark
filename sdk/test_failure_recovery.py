
import time
from datetime import datetime, timezone

from queryshark.client import QuerySharkClient

TOTAL_RECORDS = 1000
WAIT_TIMEOUT = 300

client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000",
    batch_size=100,
    request_timeout=5
)

records = []

for i in range(TOTAL_RECORDS):
    records.append({
        "sql_text": f"SELECT {i}",
        "current_schema": "queryshark_recovery_test",
        "duration_ms": 15.5,
        "total_elapsed_ms": 16.2,
        "status": "FAST",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

accepted = client.send_telemetry_batch(records)

print(f"Records accepted: {accepted}")
print(f"Records pending: {client.pending_count()}")

print("\nBackend is expected to be offline.")
print("Restart your FastAPI backend in the other terminal.")
print("Waiting for telemetry delivery...")

deadline = time.perf_counter() + WAIT_TIMEOUT

while client.pending_count() > 0 and time.perf_counter() < deadline:
    time.sleep(1)

remaining = client.pending_count()

client.close()

print("\n========== FAILURE RECOVERY RESULTS ==========")
print(f"Records accepted: {accepted}")
print(f"Records remaining: {remaining}")

if accepted == TOTAL_RECORDS and remaining == 0:
    print("RESULT: SUCCESS - All records recovered and delivered.")
else:
    print("RESULT: INCOMPLETE - Some records remain in SQLite.")
