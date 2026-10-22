from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

class QueryRankingOption(str, Enum):
    """Supported ranking criteria for query performance analysis."""
    DURATION_DESC = "duration_desc"           # Slowest to fastest (Top Bottlenecks)
    DURATION_ASC = "duration_asc"             # Fastest to slowest
    EXECUTION_ORDER = "execution_order"       # Sequential order in script/file
    STATUS = "status"                         # Slow queries first, then Fast
    ROWS_AFFECTED_DESC = "rows_affected_desc" # Highest rows affected first
    TIMESTAMP_DESC = "timestamp_desc"         # Most recent execution first
    TIMESTAMP_ASC = "timestamp_asc"           # Oldest execution first

class QueryExecuteRequest(BaseModel):
    """Payload for single query execution."""
    sql_query: str = Field(
        ...,
        description="SQL command to execute",
        json_schema_extra={"example": "SELECT * FROM users WHERE id = 123;"}
    )
    schema_name: Optional[str] = Field(
        "default",
        description="Target database schema",
        json_schema_extra={"example": "queryshark_db"}
    )

class QueryRunRecord(BaseModel):
    """Database entity representation of an intercepted query run."""
    model_config = ConfigDict(from_attributes=True)

    queryID: int
    sql_text: str
    current_schema: str
    duration_ms: Optional[float] = None
    total_elapsed_ms: Optional[float] = None    
    status: str
    timestamp: datetime

class QueryExecuteResponse(BaseModel):
    """Response payload for single query execution."""
    query_record: QueryRunRecord
    rows_affected: int
    results: Optional[List[Any]] = None
    error: Optional[str] = None

class BatchStatementResult(BaseModel):
    """Execution and ranking metrics for an individual statement within a .sql file or script."""
    rank: int = Field(default = 0)
    statement_index: int
    sql_text: str
    duration_ms: float
    total_elapsed_ms: float
    status: str
    rows_affected: int = 0
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    timestamp: datetime = Field(default_factory=datetime.now)
    queryID: Optional[int] = None

class BatchExecutionSummary(BaseModel):
    """Statistical summary across all statements executed in a batch/file."""
    total_statements: int
    successful_statements: int
    failed_statements: int
    slow_statements: int
    fast_statements: int
    total_duration_ms: float
    avg_duration_ms: float
    max_duration_ms: float
    min_duration_ms: float
    slow_percentage: float
    unavailable_statements: int
    total_elapsed_ms: float
    avg_total_elapsed_ms: float

class BatchQueryExecuteResponse(BaseModel):
    """Complete response payload for .sql file upload and batch execution with ranking."""
    filename: Optional[str] = None
    ranking_criterion: str
    summary: BatchExecutionSummary
    statements: List[BatchStatementResult]

class BatchScriptExecuteRequest(BaseModel):
    """Payload for executing a raw multi-statement SQL script."""
    sql_script: str = Field(
        ...,
        description="Multi-statement SQL script text",
        json_schema_extra={"example": "SELECT 1; SELECT SLEEP(0.12);"}
    )
    schema_name: Optional[str] = Field("default", description="Target database schema")
    rank_by: QueryRankingOption = Field(QueryRankingOption.DURATION_DESC, description="Ranking criterion for response")

class QuerySummaryStats(BaseModel):
    """Global query performance health metrics."""
    total_queries: int
    slow_queries: int
    fast_queries: int
    avg_duration_ms: float
    slow_percentage: float