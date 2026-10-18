import csv
import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.db.connection import DatabasePool

router = APIRouter()

@router.get("/csv")
def export_queries_csv():
    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Query ID", "SQL Query", "Schema", "Duration (ms)", "Status", "Timestamp"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        query = "SELECT queryID, sql_text, current_schema, duration_ms, status, timestamp FROM QueryRuns ORDER BY timestamp DESC"
        with DatabasePool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            for row in cursor:
                writer.writerow([
                    row["queryID"],
                    row["sql_text"],
                    row["current_schema"],
                    row["duration_ms"],
                    row["status"],
                    row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
            cursor.close()

    headers = {'Content-Disposition': 'attachment; filename="queryshark_report.csv"'}
    return StreamingResponse(iter_csv(), media_type="text/csv", headers=headers)