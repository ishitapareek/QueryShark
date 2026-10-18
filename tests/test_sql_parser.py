import pytest
from app.services.sql_parser import SQLParserService
from app.models.query_model import QueryRankingOption

def test_split_sql_statements_basic():
    script = """
    -- Query 1
    SELECT * FROM users;
    # Query 2
    SELECT SLEEP(0.1);
    /* Block comment
       spanning multiple lines */
    INSERT INTO logs (msg) VALUES ('Completed;');
    """
    statements = SQLParserService.split_sql_statements(script)
    assert len(statements) == 3
    assert statements[0] == "SELECT * FROM users"
    assert statements[1] == "SELECT SLEEP(0.1)"
    assert statements[2] == "INSERT INTO logs (msg) VALUES ('Completed;')"

def test_split_sql_empty():
    assert SQLParserService.split_sql_statements("") == []
    assert SQLParserService.split_sql_statements("   -- only comment\n  ") == []

def test_rank_statements_duration_desc():
    sample = [
        {"statement_index": 1, "duration_ms": 15.0, "status": "FAST"},
        {"statement_index": 2, "duration_ms": 250.0, "status": "SLOW"},
        {"statement_index": 3, "duration_ms": 80.0, "status": "FAST"}
    ]
    ranked = SQLParserService.rank_statements(sample, rank_by="duration_desc")
    assert ranked[0]["rank"] == 1
    assert ranked[0]["statement_index"] == 2
    assert ranked[0]["duration_ms"] == 250.0

    assert ranked[1]["rank"] == 2
    assert ranked[1]["statement_index"] == 3

    assert ranked[2]["rank"] == 3
    assert ranked[2]["statement_index"] == 1

def test_rank_statements_duration_asc():
    sample = [
        {"statement_index": 1, "duration_ms": 15.0, "status": "FAST"},
        {"statement_index": 2, "duration_ms": 250.0, "status": "SLOW"},
        {"statement_index": 3, "duration_ms": 80.0, "status": "FAST"}
    ]
    ranked = SQLParserService.rank_statements(sample, rank_by="duration_asc")
    assert ranked[0]["rank"] == 1
    assert ranked[0]["duration_ms"] == 15.0

def test_rank_statements_execution_order():
    sample = [
        {"statement_index": 3, "duration_ms": 15.0, "status": "FAST"},
        {"statement_index": 1, "duration_ms": 250.0, "status": "SLOW"},
        {"statement_index": 2, "duration_ms": 80.0, "status": "FAST"}
    ]
    ranked = SQLParserService.rank_statements(sample, rank_by="execution_order")
    assert [r["statement_index"] for r in ranked] == [1, 2, 3]
