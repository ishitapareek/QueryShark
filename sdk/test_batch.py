
import time

from queryshark.client import QuerySharkClient

client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000",
    batch_size=100
)

for i in range(10):
    client.send_telemetry({
        "sql_text": f"SELECT {i}",
        "current_schema": "test_db",
        "duration_ms": 10.5,
        "total_elapsed_ms": 11.2,
        "status": "FAST",
        "timestamp": "2026-11-27T12:00:00+00:00"
    })

print("Queued records:", client.pending_count())

# Give the background worker time to deliver the batch.
for _ in range(30):
    if client.pending_count() == 0:
        break
    time.sleep(0.5)

print("Remaining records:", client.pending_count())

client.close()
