import mysql.connector

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "admin",
    "database": "QueryShark"
}

def main():

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary = True)

    try:

        query = "SELECT * FROM QueryRuns LIMIT 5;"

        cursor.execute(query)

        if query.startswith("SELECT"):
            cursor.fetchall()

        connection_id = conn.connection_id

        # Finds the most recent completed query 
        cursor.execute("""
            SELECT
                e.SQL_TEXT,
                e.CURRENT_SCHEMA,
                e.TIMER_WAIT / 1000000000 AS duration_ms
            FROM performance_schema.events_statements_history e
            JOIN performance_schema.threads t ON e.THREAD_ID = t.THREAD_ID
            WHERE t.PROCESSLIST_ID = %s
            ORDER BY e.EVENT_ID DESC
            LIMIT 1
        """, (connection_id,))

        result = cursor.fetchone()

        sql_text = result["SQL_TEXT"]
        schema = result["CURRENT_SCHEMA"]
        duration = result["duration_ms"]
        status = "SLOW" if duration > 100 else "FAST"

        print("Query:", sql_text)
        print("Schema:", schema)
        print("Time:", duration, "ms")
        print("Status:", status)

        cursor.execute("""
            INSERT INTO QueryRuns
                (current_schema, sql_text, duration_ms, status)
            VALUES
                (%s, %s, %s, %s)
        """, (schema, sql_text, duration, status))

        conn.commit()

    except mysql.connector.Error as err:
        print("Error: ", err)

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()