
import time
import mysql.connector

from queryshark import (
    QuerySharkClient,
    instrument_connection
)


# Connect to the QueryShark agent.
client = QuerySharkClient(
    agent_url="http://127.0.0.1:8000"
)

# Connect to the application's MySQL database.
connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="queryshark"
)

# Instrument the connection.
connection = instrument_connection(
    connection,
    on_query=client.send_telemetry
)

try:
    cursor = connection.cursor()

    cursor.execute("SELECT 1")

    print("Query result:", cursor.fetchone())

    cursor.close()

finally:
    connection.close()

    # Wait for telemetry to reach QueryShark.
    client.close()

print("QueryShark monitoring completed.")
