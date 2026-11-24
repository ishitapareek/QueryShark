import mysql.connector

from queryshark.performance import PerformanceSchemaMonitor


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
    monitoring_connection=monitor_connection,
    application_connection_id=app_connection.connection_id
)

try:
    thread_id = monitor.get_thread_id()

    print("Application Thread ID:", thread_id)

    baseline = monitor.get_baseline()

    print("Baseline Event ID:", baseline)

    cursor = app_connection.cursor()
    cursor.execute("SELECT SLEEP(0.2)")
    cursor.fetchone()
    cursor.close()

    duration = monitor.get_statement_duration_ms(baseline)

    print("Server-side execution time:", duration, "ms")

finally:
    app_connection.close()
    monitor_connection.close()