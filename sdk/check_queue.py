
from queryshark.storage import SQLiteTelemetryQueue

queue = SQLiteTelemetryQueue()

print("SQLite database:", queue.db_path)
print("Pending records:", queue.pending_count())

records = queue.get_batch(batch_size=10)

print("\nPending telemetry records:")

for item in records:
    print(
        f"ID: {item['id']} | "
        f"Attempts: {item['attempts']} | "
        f"Record: {item['record']}"
    )
