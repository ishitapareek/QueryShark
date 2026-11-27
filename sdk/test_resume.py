
import time

from queryshark.client import QuerySharkClient

client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000",
    batch_size=100,
    request_timeout=10
)

print("Resuming previously stored telemetry...")
print("Pending records:", client.pending_count())

deadline = time.perf_counter() + 300

while client.pending_count() > 0 and time.perf_counter() < deadline:
    time.sleep(1)

remaining = client.pending_count()
client.close()

print("\n========== RECOVERY RESULTS ==========")
print("Records remaining:", remaining)

if remaining == 0:
    print("RESULT: SUCCESS - Previously stored records recovered.")
else:
    print("RESULT: INCOMPLETE - Records remain safely stored.")
