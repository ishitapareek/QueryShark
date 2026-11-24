
import mysql.connector

from queryshark import (
    QuerySharkClient,
    instrument_connection
)

from queryshark.performance import PerformanceSchemaMonitor


client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000"
)

app_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="queryshark"
)

monitor_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="queryshark"
)

monitor = PerformanceSchemaMonitor(
    monitor_connection,
    app_connection.connection_id
)

connection = instrument_connection(
    app_connection,
    on_query=client.send_telemetry,
    performance_monitor=monitor,
    slow_threshold_ms=100.0
)

try:
    cursor = connection.cursor()

    cursor.execute("SELECT 2")
    print("Normal query:", cursor.fetchone())

    cursor.execute("SELECT SLEEP(0.15)")
    print("Sleep query:", cursor.fetchone())

    cursor.close()

finally:
    connection.close()
    monitor_connection.close()
    client.close()

print("SDK monitoring completed.")
