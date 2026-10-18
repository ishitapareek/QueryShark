import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from typing import Dict, Any, List

API_BASE_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="QueryShark — Database Performance & Bottleneck Engine",
    page_icon="🦈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        border-left: 4px solid #007bff;
    }
    .status-slow {
        color: #d9534f;
        font-weight: bold;
    }
    .status-fast {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #e0a800;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("🦈 QueryShark — Query Performance & Profiling Engine")
st.caption("Real-time database query telemetry, SLA threshold monitoring, and multi-query batch ranking")

# Sidebar Controls
st.sidebar.header("⚙️ Global Settings & Filters")
status_filter = st.sidebar.selectbox("Filter History by Status", ["ALL", "SLOW", "FAST"])
history_rank = st.sidebar.selectbox(
    "Rank History By",
    [
        ("⏱️ Slowest First (Latency)", "duration_desc"),
        ("⚡ Fastest First", "duration_asc"),
        ("🕒 Most Recent First", "timestamp_desc"),
        ("⏳ Oldest First", "timestamp_asc"),
        ("⚠️ Status (Slow First)", "status")
    ],
    format_func=lambda x: x[0]
)[1]
limit = st.sidebar.slider("Query Fetch Limit", 10, 500, 100)
st.sidebar.divider()
st.sidebar.info("💡 **Slow Threshold:** Queries exceeding **100ms** are automatically flagged as **SLOW**.")

# Fetch Summary Telemetry Metrics
summary_data = None
backend_online = False
try:
    summary_res = requests.get(f"{API_BASE_URL}/queries/summary", timeout=3)
    if summary_res.status_code == 200:
        summary_data = summary_res.json()
        backend_online = True
    else:
        st.sidebar.warning(f"Backend API status: {summary_res.status_code}")
except Exception:
    st.sidebar.error("⚠️ Backend API Offline. Ensure FastAPI is running on `http://localhost:8000`.")

# Top Telemetry Cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Queries Tracked", summary_data["total_queries"] if summary_data else 0)
col2.metric("Slow Queries (>100ms)", summary_data["slow_queries"] if summary_data else 0)
col3.metric("Avg Latency", f"{summary_data['avg_duration_ms']} ms" if summary_data else "0 ms")
col4.metric("Slow Query Ratio", f"{summary_data['slow_percentage']}%" if summary_data else "0%")

st.divider()

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📁 Upload .SQL File & Rank",
    "⚡ Single Query Runner",
    "📊 Query History & Analytics",
    "🔥 Slow Query Hall of Shame"
])

# -------------------------------------------------------------
# TAB 1: Upload .SQL File & Rank
# -------------------------------------------------------------
with tab1:
    st.subheader("📁 Upload SQL File — Batch Execution & Bottleneck Ranking")
    st.write(
        "Upload a `.sql` file containing multiple SQL statements. The engine will parse each statement, "
        "execute it via the interceptor, measure precise latency, evaluate SLA thresholds, and rank each query."
    )

    col_upload, col_opts = st.columns([2, 1])

    with col_upload:
        uploaded_file = st.file_uploader("Select .sql file to upload", type=["sql", "txt"])
        
        # Optional fallback to paste multi-statement script directly
        with st.expander("Or paste multi-statement SQL script manually"):
            pasted_script = st.text_area(
                "SQL Script",
                height=140,
                placeholder="SELECT 1;\nSELECT SLEEP(0.12);\nSELECT 100;\n-- More statements..."
            )

    with col_opts:
        target_schema = st.text_input("Target Schema", "default", help="MySQL schema to execute against")
        
        ranking_choice = st.radio(
            "Options to Rank Queries:",
            [
                ("⏱️ Slowest to Fastest (Bottlenecks)", "duration_desc"),
                ("⚡ Fastest to Slowest", "duration_asc"),
                ("📜 Execution Order (File Sequence)", "execution_order"),
                ("⚠️ Status (Slow & Error First)", "status"),
                ("📊 Rows Affected (Highest First)", "rows_affected_desc")
            ],
            format_func=lambda x: x[0]
        )[1]

    execute_btn = st.button("🚀 Execute & Rank Statements", type="primary")

    if execute_btn:
        if not uploaded_file and not pasted_script.strip():
            st.warning("Please upload a `.sql` file or paste a SQL script to execute.")
        else:
            with st.spinner("Parsing SQL statements, intercepting execution & computing ranking metrics..."):
                try:
                    if uploaded_file:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/sql")}
                        data = {"schema_name": target_schema, "rank_by": ranking_choice}
                        res = requests.post(f"{API_BASE_URL}/queries/upload-sql", files=files, data=data, timeout=60)
                    else:
                        payload = {
                            "sql_script": pasted_script,
                            "schema_name": target_schema,
                            "rank_by": ranking_choice
                        }
                        res = requests.post(f"{API_BASE_URL}/queries/execute-script", json=payload, timeout=60)

                    if res.status_code == 200:
                        batch_res = res.json()
                        st.session_state["last_batch_result"] = batch_res
                        st.success(f"Batch execution completed for {batch_res.get('filename', 'script')}!")
                    else:
                        st.error(f"Execution failed ({res.status_code}): {res.text}")
                except Exception as ex:
                    st.error(f"Error communicating with backend: {ex}")

    # Render Batch Execution Results
    if "last_batch_result" in st.session_state:
        batch_data = st.session_state["last_batch_result"]
        summary = batch_data.get("summary", {})
        statements = batch_data.get("statements", [])

        st.subheader("📊 Batch Summary & Performance Aggregates")
        b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)
        b_col1.metric("Statements Executed", summary.get("total_statements", 0))
        b_col2.metric("Slow Statements (>100ms)", summary.get("slow_statements", 0))
        b_col3.metric("Errors / Failures", summary.get("failed_statements", 0))
        b_col4.metric("Avg Latency", f"{summary.get('avg_duration_ms', 0)} ms")
        b_col5.metric("Max Latency (Peak)", f"{summary.get('max_duration_ms', 0)} ms")

        # Interactive Ranking Switcher (allows instant re-ranking without re-running!)
        st.markdown("#### 🎯 Interactive Statement Ranking")
        rerank_opt = st.selectbox(
            "Change View Ranking:",
            [
                ("⏱️ Slowest to Fastest (Bottleneck Priority)", "duration_desc"),
                ("⚡ Fastest to Slowest", "duration_asc"),
                ("📜 File Execution Order", "execution_order"),
                ("⚠️ Status Priority (Slow/Error First)", "status"),
                ("📊 Rows Affected (Descending)", "rows_affected_desc")
            ],
            format_func=lambda x: x[0]
        )[1]

        # In-memory dynamic re-ranking for instantaneous feedback
        df_batch = pd.DataFrame(statements)
        if not df_batch.empty:
            if rerank_opt == "duration_desc":
                df_batch = df_batch.sort_values(by="duration_ms", ascending=False)
            elif rerank_opt == "duration_asc":
                df_batch = df_batch.sort_values(by="duration_ms", ascending=True)
            elif rerank_opt == "execution_order":
                df_batch = df_batch.sort_values(by="statement_index", ascending=True)
            elif rerank_opt == "status":
                status_order = {"SLOW": 0, "ERROR": 1, "FAST": 2}
                df_batch["status_p"] = df_batch["status"].map(lambda s: status_order.get(s, 3))
                df_batch = df_batch.sort_values(by=["status_p", "duration_ms"], ascending=[True, False]).drop(columns=["status_p"])
            elif rerank_opt == "rows_affected_desc":
                df_batch = df_batch.sort_values(by="rows_affected", ascending=False)

            # Assign 1..N rank badges
            df_batch["Rank"] = range(1, len(df_batch) + 1)
            rank_badges = {1: "🥇 #1", 2: "🥈 #2", 3: "🥉 #3"}
            df_batch["Rank Badge"] = df_batch["Rank"].apply(lambda r: rank_badges.get(r, f"#{r}"))

            # Latency Bar Chart
            fig_batch = px.bar(
                df_batch,
                x="Rank Badge",
                y="duration_ms",
                color="status",
                color_discrete_map={"FAST": "#28a745", "SLOW": "#dc3545", "ERROR": "#ffc107"},
                hover_data=["statement_index", "sql_text", "rows_affected"],
                title="Statement Latency Distribution by Rank (ms)",
                labels={"duration_ms": "Latency (ms)", "Rank Badge": "Query Rank"}
            )
            fig_batch.add_hline(y=100.0, line_dash="dash", line_color="red", annotation_text="100ms SLA Limit")
            st.plotly_chart(fig_batch, use_container_width=True)

            # Table display
            display_cols = ["Rank Badge", "statement_index", "duration_ms", "status", "rows_affected", "sql_text"]
            st.dataframe(
                df_batch[display_cols].rename(columns={
                    "Rank Badge": "Rank",
                    "statement_index": "Stmt #",
                    "duration_ms": "Duration (ms)",
                    "status": "Status",
                    "rows_affected": "Rows",
                    "sql_text": "SQL Statement Preview"
                }),
                use_container_width=True
            )

            with st.expander("🔍 Deep-Dive: Statement Inspection & Errors"):
                for _, row in df_batch.iterrows():
                    status_color = "red" if row["status"] == "SLOW" else ("orange" if row["status"] == "ERROR" else "green")
                    st.markdown(
                        f"**{row['Rank Badge']}** | Statement #{row['statement_index']} — "
                        f"<span style='color:{status_color}; font-weight:bold;'>{row['status']}</span> "
                        f"({row['duration_ms']} ms, {row['rows_affected']} rows)",
                        unsafe_allow_html=True
                    )
                    st.code(row["sql_text"], language="sql")
                    if row.get("error"):
                        st.error(f"Error: {row['error']}")
                    st.divider()

# -------------------------------------------------------------
# TAB 2: Single Query Runner
# -------------------------------------------------------------
with tab2:
    st.subheader("⚡ Single Query Runner")
    st.write("Execute an individual SQL command to test immediate interception latency, status, and output.")

    col_sq1, col_sq2 = st.columns([3, 1])
    with col_sq1:
        single_sql = st.text_area(
            "Enter SQL Command",
            value="SELECT SLEEP(0.15) as simulated_slow_query;",
            height=120,
            help="Type any valid SQL statement"
        )
    with col_sq2:
        single_schema = st.text_input("Target Schema", "default", key="single_schema_input")
        run_single_btn = st.button("▶️ Execute Command", type="primary", use_container_width=True)

    if run_single_btn:
        if not single_sql.strip():
            st.warning("Please provide a SQL query to execute.")
        else:
            with st.spinner("Executing and intercepting query..."):
                try:
                    payload = {"sql_query": single_sql, "schema_name": single_schema}
                    res = requests.post(f"{API_BASE_URL}/queries/execute", json=payload, timeout=30)
                    if res.status_code == 200:
                        exec_data = res.json()
                        rec = exec_data.get("query_record", {})
                        dur = rec.get("duration_ms", 0.0)
                        st_status = rec.get("status", "FAST")
                        err = exec_data.get("error")

                        if err:
                            st.error(f"❌ Execution Error: {err}")
                        elif st_status == "SLOW":
                            st.error(f"⚠️ Query Executed in **{dur} ms** — Marked as **SLOW** (>100ms threshold breach)!")
                        else:
                            st.success(f"✅ Query Executed in **{dur} ms** — Marked as **FAST**!")

                        res_c1, res_c2, res_c3 = st.columns(3)
                        res_c1.metric("Query ID", rec.get("queryID", "-"))
                        res_c2.metric("Latency", f"{dur} ms")
                        res_c3.metric("Rows Affected", exec_data.get("rows_affected", 0))

                        # Display Query Results
                        results = exec_data.get("results")
                        if results:
                            st.markdown("#### Query Output Result Set:")
                            st.dataframe(pd.DataFrame(results), use_container_width=True)
                        else:
                            st.info("Query completed successfully with no tabular result set.")
                    else:
                        st.error(f"Execution failed with status code {res.status_code}: {res.text}")
                except Exception as err:
                    st.error(f"Failed to communicate with backend: {err}")

# -------------------------------------------------------------
# TAB 3: Query History & Analytics
# -------------------------------------------------------------
with tab3:
    st.subheader("📊 Query Telemetry History")
    st.write("Browse historically captured queries with custom ranking and filtering.")

    params = {"limit": limit, "rank_by": history_rank}
    if status_filter != "ALL":
        params["status"] = status_filter

    try:
        res = requests.get(f"{API_BASE_URL}/queries/", params=params, timeout=5)
        if res.status_code == 200 and res.json():
            df_history = pd.DataFrame(res.json())

            # Highlight status column
            def highlight_status(val):
                if val == 'SLOW':
                    return 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold;'
                return 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold;'

            st.dataframe(
                df_history.style.map(highlight_status, subset=['status']),
                use_container_width=True
            )

            # Scatter Timeline Chart
            fig_hist = px.scatter(
                df_history,
                x='timestamp',
                y='duration_ms',
                color='status',
                color_discrete_map={'FAST': '#28a745', 'SLOW': '#dc3545'},
                hover_data=['sql_text', 'queryID', 'current_schema'],
                title=f"Query Execution Timeline (Ranked by {history_rank})"
            )
            fig_hist.add_hline(y=100.0, line_dash="dash", line_color="red", annotation_text="100ms Threshold")
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No query logs matching current filters found.")
    except Exception as err:
        st.error(f"Error fetching query history: {err}")

    # CSV Download Button
    try:
        csv_res = requests.get(f"{API_BASE_URL}/export/csv", timeout=5)
        if csv_res.status_code == 200:
            st.download_button(
                label="📥 Download Historical Report (CSV)",
                data=csv_res.content,
                file_name="queryshark_telemetry_report.csv",
                mime="text/csv"
            )
    except Exception:
        st.button("📥 Download Historical Report (CSV)", disabled=True)

# -------------------------------------------------------------
# TAB 4: Top Slow Queries (Hall of Shame)
# -------------------------------------------------------------
with tab4:
    st.subheader("🔥 Slow Query Bottlenecks (Top 10 Latency Outliers)")
    st.write("Identifies top queries that consistently violated the 100ms performance threshold.")

    try:
        slow_res = requests.get(f"{API_BASE_URL}/queries/slow?limit=10", timeout=5)
        if slow_res.status_code == 200 and slow_res.json():
            df_slow = pd.DataFrame(slow_res.json())
            
            # Bar chart
            fig_slow = px.bar(
                df_slow,
                x='queryID',
                y='duration_ms',
                color='duration_ms',
                color_continuous_scale='Reds',
                hover_data=['sql_text', 'timestamp'],
                title="Top Slow Queries by Execution Duration (ms)",
                labels={'duration_ms': 'Latency (ms)', 'queryID': 'Query ID'}
            )
            st.plotly_chart(fig_slow, use_container_width=True)

            st.table(df_slow[['queryID', 'duration_ms', 'status', 'sql_text', 'timestamp']])
        else:
            st.info("No slow queries (>100ms) recorded yet. System running smoothly!")
    except Exception as err:
        st.error(f"Error loading slow queries: {err}")