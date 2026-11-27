
from queryshark.storage import SQLiteTelemetryQueue


queue = SQLiteTelemetryQueue(
    db_path="test_telemetry.db",
    max_records=5
)

# Add sample telemetry
for i in range(3):
    record = {
        "sql_text": f"SELECT {i + 1}",
        "duration_ms": 10.5,
        "status": "FAST"
    }

    result = queue.enqueue(record)
    print(f"Record {i + 1} stored:", result)


# Check pending records
print("\nPending records:", queue.pending_count())


# Retrieve a batch
batch = queue.get_batch(batch_size=2)

print("\nRetrieved batch:")

for item in batch:
    print(item)


# Simulate failed delivery
record_ids = [item["id"] for item in batch]

queue.mark_failed(
    record_ids,
    "Backend unavailable"
)

print("\nAfter failed delivery:")
print("Pending records:", queue.pending_count())


# Simulate successful delivery
queue.acknowledge(record_ids)

print("\nAfter successful delivery:")
print("Pending records:", queue.pending_count())
