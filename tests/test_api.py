import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_single_query_execution():
    payload = {
        "sql_query": "SELECT 123 AS num_val;",
        "schema_name": "default"
    }
    response = client.post("/api/v1/queries/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "query_record" in data
    assert data["query_record"]["sql_text"] == "SELECT 123 AS num_val;"
    assert data["rows_affected"] == 1
    assert data["results"] == [{"num_val": 123}]

def test_upload_sql_file():
    sql_script = "SELECT 10;\nSELECT 20;\nSELECT 30;"
    file_bytes = io.BytesIO(sql_script.encode("utf-8"))
    
    response = client.post(
        "/api/v1/queries/upload-sql",
        files={"file": ("sample.sql", file_bytes, "application/sql")},
        data={"rank_by": "duration_desc"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "sample.sql"
    assert data["summary"]["total_statements"] == 3
    assert len(data["statements"]) == 3
    assert data["statements"][0]["rank"] == 1

def test_execute_script_endpoint():
    payload = {
        "sql_script": "SELECT 1; SELECT 2;",
        "schema_name": "default",
        "rank_by": "duration_asc"
    }
    response = client.post("/api/v1/queries/execute-script", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_statements"] == 2
    assert len(data["statements"]) == 2

def test_get_queries_and_summary():
    res_list = client.get("/api/v1/queries/?limit=10&rank_by=duration_desc")
    assert res_list.status_code == 200
    assert isinstance(res_list.json(), list)

    res_summary = client.get("/api/v1/queries/summary")
    assert res_summary.status_code == 200
    assert "total_queries" in res_summary.json()

def test_export_csv():
    response = client.get("/api/v1/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "Query ID,SQL Query,Schema,Duration (ms),Status,Timestamp" in response.text
