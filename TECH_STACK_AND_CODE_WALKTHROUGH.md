# 🛠️ QueryShark — Technology Stack & File-by-File Code Walkthrough

An in-depth technical reference explaining every library chosen for **QueryShark**, why it was selected over industry alternatives, and a structural code walkthrough detailing the purpose and mechanics of every file in the project.

---

## 📑 Table of Contents
1. [Technology Stack & Library Justification](#1-technology-stack--library-justification)
   - [Backend Core Libraries](#backend-core-libraries)
   - [Frontend & Data Visualization Libraries](#frontend--data-visualization-libraries)
   - [Testing & Quality Assurance Libraries](#testing--quality-assurance-libraries)
2. [Comparative Analysis: Why We Chose These Libraries](#2-comparative-analysis-why-we-chose-these-libraries)
3. [File-by-File Code Walkthrough](#3-file-by-file-code-walkthrough)
   - [Application Entrypoint & Lifecycle](#application-entrypoint--lifecycle)
   - [Configuration & Settings](#configuration--settings)
   - [Database Connection & Schema Layer](#database-connection--schema-layer)
   - [Data Models & Schema Contracts](#data-models--schema-contracts)
   - [Business Logic & Service Layer](#business-logic--service-layer)
   - [REST API Routing & Endpoints Layer](#rest-api-routing--endpoints-layer)
   - [Frontend Presentation Layer](#frontend-presentation-layer)
   - [Automated Testing Suite](#automated-testing-suite)
4. [How to Run and Verify the System](#4-how-to-run-and-verify-the-system)

---

## 1. Technology Stack & Library Justification

### Backend Core Libraries

#### 1. `fastapi` (>= 0.100.0)
- **Role in Project**: Serves as the primary REST API framework hosting all query execution, file upload, telemetry, and export endpoints.
- **Why We Used It**:
  - **High Throughput**: Built on Starlette and ASGI, delivering asynchronous request handling on par with NodeJS and Go.
  - **Automatic OpenAPI / Swagger Documentation**: Generates interactive documentation (`/docs`) directly from type annotations without manual schema maintenance.
  - **Native Pydantic Integration**: Validates and serializes incoming and outgoing HTTP payloads with strict type safety.

#### 2. `uvicorn[standard]` (>= 0.22.0)
- **Role in Project**: The ASGI (Asynchronous Server Gateway Interface) web server executing FastAPI.
- **Why We Used It**:
  - `uvicorn[standard]` includes `uvloop` (an ultra-fast drop-in replacement for Python's default asyncio event loop based on `libuv`) and `httptools` (fast C-based HTTP parser).
  - Handles concurrent network connections with minimal CPU overhead.

#### 3. `mysql-connector-python` (>= 8.0.33)
- **Role in Project**: The official MySQL driver establishing and maintaining connections to the MySQL database engine.
- **Why We Used It**:
  - **Native Connection Pooling**: Ships with `mysql.connector.pooling.MySQLConnectionPool`, enabling thread-safe connection reuse.
  - **Direct Driver Access**: By avoiding heavy ORMs (like SQLAlchemy or Django ORM), our latency measurements capture pure database execution and network transport time rather than ORM object-relational mapping overhead.
  - **Dictionary Cursors**: Supports returning query rows directly as Python dictionaries (`cursor(dictionary=True)`), enabling frictionless conversion to JSON and Pandas dataframes.

#### 4. `pydantic` & `pydantic-settings` (>= 2.0.0)
- **Role in Project**: Defines domain schemas, request/response models, and loads environment variables.
- **Why We Used It**:
  - **Rust-Backed Performance (`pydantic-core`)**: Pydantic V2 is up to 10x faster than traditional Python schema libraries like Marshmallow.
  - **Environment Parsing**: `pydantic-settings` automatically reads `.env` files, validates types (e.g. converting port strings to integers), and enforces required configuration.

#### 5. `python-multipart` (>= 0.0.6)
- **Role in Project**: Enables FastAPI to parse HTTP `multipart/form-data` requests.
- **Why We Used It**:
  - Required for the `UploadFile` feature in `POST /api/v1/queries/upload-sql`, streaming uploaded `.sql` files directly from memory into our parser without writing temporary files to disk.

---

### Frontend & Data Visualization Libraries

#### 6. `streamlit` (>= 1.25.0)
- **Role in Project**: Provides the entire interactive, reactive web user interface.
- **Why We Used It**:
  - **Rapid UI Development**: Allows constructing production-grade interactive dashboards in pure Python without writing separate React, HTML, or CSS codebases.
  - **Session State & Reactivity**: Retains user-uploaded batch results, allowing users to dynamically switch between ranking views (Slowest First, Fastest First, Execution Order) instantly without re-querying the database.

#### 7. `requests` (>= 2.31.0)
- **Role in Project**: The HTTP client used by the Streamlit dashboard to communicate with the FastAPI backend.
- **Why We Used It**:
  - Simple, robust, battle-tested API for sending JSON payloads, handling multipart file uploads, and downloading binary streams (such as CSV reports).

#### 8. `pandas` (>= 2.0.0)
- **Role in Project**: Data manipulation, sorting, and tabular styling.
- **Why We Used It**:
  - **High-Performance Sorting**: Powers instant in-memory re-ranking across thousands of query records in sub-millisecond time.
  - **Visual Styling**: Powers conditional styling (`df.style.map`) to highlight `SLOW` queries in red and `FAST` queries in green.

#### 9. `plotly` (>= 5.15.0)
- **Role in Project**: Generates rich, interactive charts and telemetry visualizations.
- **Why We Used It**:
  - **Interactive D3/WebGL Engine**: Users can zoom, pan, hover over individual data points to see full SQL queries, and toggle chart series.
  - **Horizontal & Vertical Bar Visualizations**: Powers the ranked bottleneck bar charts and latency distribution timelines.

---

### Testing & Quality Assurance Libraries

#### 10. `pytest` & `pytest-asyncio`
- **Role in Project**: Automated testing framework verifying parser accuracy, ranking algorithms, and API contracts.
- **Why We Used It**:
  - Concise test definitions, clear failure diffs, and native support for testing FastAPI endpoints via `TestClient`.

#### 11. `httpx` (>= 0.24.1)
- **Role in Project**: Provides the transport layer for FastAPI's `TestClient`.
- **Why We Used It**:
  - Allows executing end-to-end integration tests directly against the FastAPI application in-memory without spawning a live background server process.

---

## 2. Comparative Analysis: Why We Chose These Libraries

| Component | QueryShark Choice | Alternative Considered | Why QueryShark's Choice Won |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | Flask / Django | FastAPI is 3x faster, natively supports asynchronous I/O, auto-generates Swagger docs, and has native Pydantic validation. |
| **Database Access** | **mysql-connector-python** | SQLAlchemy ORM | SQLAlchemy adds translation overhead and object mapping latency; direct connector measures actual database wire-speed. |
| **Settings Management** | **pydantic-settings** | `os.environ` / `python-decouple` | Strict type validation, default fallback values, and `.env` parsing with zero boilerplate. |
| **Frontend Framework** | **Streamlit** | React / Angular | Eliminates Node.js toolchains, build steps, and API client glue code; unifies full stack in Python. |
| **Data Visuals** | **Plotly** | Matplotlib / Seaborn | Matplotlib renders static raster images; Plotly delivers hardware-accelerated interactive web charts. |

---

## 3. File-by-File Code Walkthrough

```
QueryStark/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── export.py        # CSV streaming export handler
│   │   │   │   │   └── queries.py       # Query execution, upload & metrics routes
│   │   │   │   └── router.py            # API V1 router aggregation
│   │   ├── core/
│   │   │   └── config.py                # Environment & application settings
│   │   ├── db/
│   │   │   ├── connection.py            # Thread-safe MySQL connection pool
│   │   │   └── schema_init.py           # Database DDL initialization & index creation
│   │   ├── models/
│   │   │   └── query_model.py           # Pydantic schemas & ranking enums
│   │   ├── services/
│   │   │   ├── interceptor.py           # Core query execution & latency measurement
│   │   │   ├── performance_schema.py    # MySQL internal performance schema diagnostics
│   │   │   └── sql_parser.py            # SQL statement isolation & ranking logic
│   │   └── main.py                      # FastAPI app entrypoint & lifespan manager
│   ├── .env.example                     # Environment template
│   └── requirements.txt                 # Backend dependencies
├── frontend/
│   ├── dashboard.py                     # Streamlit multi-tab monitoring dashboard
│   └── requirements.txt                 # Frontend dependencies
├── tests/
│   ├── test_api.py                      # Integration tests for REST endpoints
│   └── test_sql_parser.py               # Unit tests for SQL parsing and ranking
├── pytest.ini                           # Pytest configuration
└── .gitignore                           # Git hygiene rules
```

---

### Application Entrypoint & Lifecycle

#### `backend/app/main.py`
- **What it does**: The central application bootstrap for the FastAPI web server.
- **Key Responsibilities**:
  - Defines the modern `lifespan` context manager which calls `init_db()` upon server startup to ensure tables and indexes are initialized before accepting incoming traffic.
  - Instantiates `FastAPI` configured with project metadata and OpenAPI routes.
  - Adds `CORSMiddleware` with permissive defaults (`*`) so cross-origin frontends or local dev servers can communicate seamlessly.
  - Mounts the aggregated API V1 router under `/api/v1`.
  - Exposes the `/health` endpoint for liveness and container readiness probes.

---

### Configuration & Settings

#### `backend/app/core/config.py`
- **What it does**: Centralized, type-safe application configuration loader.
- **Key Responsibilities**:
  - Implements the `Settings` class inheriting from `pydantic_settings.BaseSettings`.
  - Declares database credentials (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`).
  - Configures the SLA threshold: `SLOW_QUERY_THRESHOLD_MS = 100.0`.
  - Configures connection pool dimensions: `DB_POOL_NAME = "queryshark_pool"`, `DB_POOL_SIZE = 20`.
  - Uses `SettingsConfigDict(env_file=".env", extra="ignore")` to safely load overrides from `.env` files while preserving reliable default values.

---

### Database Connection & Schema Layer

#### `backend/app/db/connection.py`
- **What it does**: Manages database connection lifecycle and pooling.
- **Key Responsibilities**:
  - Implements `DatabasePool` singleton pattern.
  - `DatabasePool.initialize()` creates a `MySQLConnectionPool` with a capacity of 20 connections and session reset flags enabled.
  - `DatabasePool.get_connection()` provides a Python `@contextmanager` that checks out a connection and guarantees its release back to the pool via a `finally: connection.close()` clause.
  - Provides `get_db()` generator for FastAPI dependency injection.

#### `backend/app/db/schema_init.py`
- **What it does**: Provisions database tables, performance indexes, and engine consumers.
- **Key Responsibilities**:
  - Creates the `QueryRuns` table with schema:
    - `queryID INT AUTO_INCREMENT PRIMARY KEY`
    - `sql_text TEXT NOT NULL`
    - `current_schema VARCHAR(100)`
    - `duration_ms FLOAT NOT NULL`
    - `status ENUM('FAST', 'SLOW') NOT NULL`
    - `timestamp DATETIME NOT NULL`
  - Defines database indexes:
    - `INDEX idx_status_time (status, timestamp)` for rapid status-filtered time-series lookups.
    - `INDEX idx_duration (duration_ms DESC)` for instantaneous top-slowest queries lookup.
  - Attempts to activate MySQL's `performance_schema.setup_consumers` for statement event logging.

---

### Data Models & Schema Contracts

#### `backend/app/models/query_model.py`
- **What it does**: Defines Pydantic data schemas, validation rules, and ranking enumerations.
- **Key Responsibilities**:
  - `QueryRankingOption` (Enum): Defines supported ranking options:
    - `DURATION_DESC`: Slowest to fastest (Top Bottlenecks)
    - `DURATION_ASC`: Fastest to slowest
    - `EXECUTION_ORDER`: Original order in script/file
    - `STATUS`: Slow and Error queries prioritized first
    - `ROWS_AFFECTED_DESC`: Highest rows affected first
    - `TIMESTAMP_DESC` / `TIMESTAMP_ASC`: Chronological order
  - `QueryExecuteRequest` / `QueryExecuteResponse`: Input and output contracts for single query execution.
  - `BatchStatementResult`: Output schema for an individual statement in a batch, including assigned rank, duration, rows affected, and error messages.
  - `BatchExecutionSummary`: Statistical aggregate summarizing total statements, slow count, fast count, error count, avg latency, max latency, and min latency.
  - `BatchQueryExecuteResponse`: Complete contract for `.sql` file upload, pairing the summary metrics with the ranked statements list.
  - `QuerySummaryStats`: Overall database query health KPIs.

---

### Business Logic & Service Layer

#### `backend/app/services/sql_parser.py`
- **What it does**: Performs lexical parsing of raw `.sql` files and executes multi-criteria ranking.
- **Key Responsibilities**:
  - `split_sql_statements(sql_content)`:
    - Scans SQL character-by-character.
    - Strips single-line comments (`--` and `#`) and multi-line comments (`/* ... */`).
    - Tracks string quotes (`'`, `"`, `` ` ``) to ensure semicolons inside strings are never mistaken for statement delimiters.
    - Returns a list of clean, executable SQL strings.
  - `rank_statements(statements, rank_by)`:
    - Sorts executed statement dictionaries according to the chosen ranking criteria.
    - Assigns an explicit 1-indexed `rank` attribute (`1, 2, 3, ...`) to each record.

#### `backend/app/services/interceptor.py`
- **What it does**: The core engine measuring query execution time, evaluating SLA breaches, and batch-profiling scripts.
- **Key Responsibilities**:
  - `execute_and_intercept(sql_query, schema_name)`:
    - Records start time using `time.perf_counter()`.
    - Borrows a connection from `DatabasePool` and executes the query.
    - Records rows affected (or fetched).
    - Catches MySQL exceptions gracefully, returning diagnostic error messages.
    - Calculates elapsed wall-clock latency in milliseconds.
    - Evaluates duration against `settings.SLOW_QUERY_THRESHOLD_MS` (100ms) to classify as `FAST` or `SLOW`.
    - Persists the execution record to `QueryRuns` via `_save_query_run()`.
  - `execute_batch_and_intercept(statements, schema_name, rank_by)`:
    - Sequentially executes every statement parsed from a `.sql` file.
    - Collects individual latencies, error states, and row counts.
    - Computes batch statistics (total duration, average, peak latency, slow percentage).
    - Calls `SQLParserService.rank_statements()` to sort and rank the results.

#### `backend/app/services/performance_schema.py`
- **What it does**: Extracts engine-level telemetry from MySQL's internal performance schema.
- **Key Responsibilities**:
  - `is_enabled()`: Verifies whether MySQL Performance Schema is turned on.
  - `get_top_digest_queries(limit)`: Queries `performance_schema.events_statements_summary_by_digest` to find top resource-intensive query templates, converting picosecond timer waits into milliseconds.

---

### REST API Routing & Endpoints Layer

#### `backend/app/api/v1/router.py`
- Aggregates child routers (`queries.router` and `export.router`) into a unified `api_router`.

#### `backend/app/api/v1/endpoints/queries.py`
- **What it does**: Exposes all query-related REST endpoints.
- **Key Endpoints**:
  - `POST /execute`: Executes a single SQL query and returns latency, rows affected, and tabular results.
  - `POST /upload-sql`: Accepts `.sql` file uploads (`UploadFile`), parses statements, executes batch interception, and returns ranked statements with summary statistics.
  - `POST /execute-script`: Accepts raw multi-statement text scripts for batch execution and ranking.
  - `GET /`: Lists historically captured queries with filtering (`status`) and ranking (`rank_by=duration_desc`, etc.).
  - `GET /slow`: Returns the top slowest queries (>100ms).
  - `GET /summary`: Returns overall database performance statistics (total, slow, fast, avg latency, slow percentage).
  - `GET /performance-schema`: Returns internal MySQL performance schema digest telemetry.

#### `backend/app/api/v1/endpoints/export.py`
- **What it does**: Streams query audit logs in CSV format.
- **Key Responsibilities**:
  - `export_queries_csv()` uses an in-memory generator (`io.StringIO`) and `StreamingResponse` to stream rows directly from MySQL to the HTTP response, avoiding high memory consumption even with large datasets.

---

### Frontend Presentation Layer

#### `frontend/dashboard.py`
- **What it does**: The interactive Streamlit web dashboard.
- **Key Components**:
  - **Sidebar Controls**: Global status filters (`ALL`, `SLOW`, `FAST`), history ranking selector, and query fetch slider.
  - **Top Telemetry Cards**: 4 live KPI cards displaying Total Queries, Slow Queries (>100ms), Avg Latency, and Slow Ratio.
  - **Tab 1: Upload .SQL File & Rank**:
    - File uploader for `.sql` and `.txt` files.
    - Fallback text area to paste multi-statement SQL scripts directly.
    - Radio buttons offering ranking options:
      - ⏱️ Slowest to Fastest (Bottlenecks)
      - ⚡ Fastest to Slowest
      - 📜 Execution Order (File Sequence)
      - ⚠️ Status (Slow & Error First)
      - 📊 Rows Affected (Highest First)
    - Batch summary cards (Total statements, Slow statements, Errors, Avg Latency, Max Latency).
    - Dynamic re-ranking dropdown allowing users to switch ranking criteria instantly on the client side without re-running queries.
    - Interactive Plotly bar chart with red dashed line indicating the 100ms SLA limit.
    - Ranked data table with rank badges (🥇 #1, 🥈 #2, 🥉 #3) and expandable statement inspection cards.
  - **Tab 2: Single Query Runner**:
    - Text area to write any SQL command (e.g. `SELECT SLEEP(0.15);`).
    - Target schema selector and execute button.
    - Instant latency readout, FAST/SLOW status indicator, and rendered result set table.
  - **Tab 3: Query History & Analytics**:
    - Dataframe of historical runs with color-coded status cells.
    - Scatter plot timeline tracking latency over time.
    - Download CSV report button.
  - **Tab 4: Slow Query Hall of Shame**:
    - Visual bar chart and table of top slowest queries ever recorded by the system.

---

### Automated Testing Suite

#### `pytest.ini`
- Configures pytest with `pythonpath = backend` and `testpaths = tests`.

#### `tests/test_sql_parser.py`
- Unit tests verifying:
  - Statement splitting ignoring single-line and multi-line comments.
  - Preservation of semicolons inside quoted string literals.
  - Ranking algorithms (`duration_desc`, `duration_asc`, `execution_order`).

#### `tests/test_api.py`
- Integration tests using FastAPI `TestClient`:
  - `GET /health` liveness probe.
  - `POST /api/v1/queries/execute` single command execution.
  - `POST /api/v1/queries/upload-sql` file upload with batch execution and ranking.
  - `POST /api/v1/queries/execute-script` multi-statement execution.
  - `GET /api/v1/queries/` and `GET /api/v1/queries/summary`.
  - `GET /api/v1/export/csv` streaming download.

---

## 4. How to Run and Verify the System

### Prerequisites
- Python 3.10+ (tested on Python 3.14.6)
- MySQL Server running locally on port 3306 with database `queryshark_db`.

### Step 1: Install Dependencies
```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Frontend dependencies
pip install -r frontend/requirements.txt
```

### Step 2: Configure Environment (Optional)
Copy `backend/.env.example` to `backend/.env` if database credentials differ from defaults:
```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=shreyansh
MYSQL_DATABASE=queryshark_db
SLOW_QUERY_THRESHOLD_MS=100.0
```

### Step 3: Run the Test Suite
```bash
python -m pytest
```
*All 11 unit and integration tests should pass.*

### Step 4: Launch the FastAPI Backend
```bash
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
- Interactive Swagger API Documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Step 5: Launch the Streamlit Monitoring Dashboard
In a new terminal:
```bash
streamlit run frontend/dashboard.py
```
- Dashboard opens in your browser at `http://localhost:8501`.

---

*Authored for the QueryShark Engineering & Architecture Team.*
