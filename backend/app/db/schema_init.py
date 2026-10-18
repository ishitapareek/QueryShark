from mysql.connector import cursor_cext
import logging
from app.db.connection import DatabasePool

logger = logging.getLogger(__name__)

CREATE_QUERYRUNS_TABLE = """
CREATE TABLE IF NOT EXISTS QueryRuns (
    queryID INT AUTO_INCREMENT PRIMARY KEY,
    sql_text TEXT NOT NULL,
    current_schema VARCHAR(100) DEFAULT 'default',
    duration_ms FLOAT NULL,
    total_elapsed_ms FLOAT NULL,
    status ENUM('FAST', 'SLOW') NOT NULL,
    timestamp DATETIME NOT NULL,
    INDEX idx_status_time (status, timestamp),
    INDEX idx_duration (duration_ms DESC)
) ENGINE=InnoDB;
"""

ENABLE_PERFORMANCE_SCHEMA = """
UPDATE performance_schema.setup_consumers 
SET ENABLED = 'YES' 
WHERE NAME LIKE 'events_statements%';
"""

def init_db():
    DatabasePool.initialize()
    with DatabasePool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(CREATE_QUERYRUNS_TABLE)
            
            # Add total_elapsed_ms to existing installations.
            cursor.execute(
                "SHOW COLUMNS FROM QueryRuns LIKE 'total_elapsed_ms'"
            )
            if cursor.fetchone() is None:
                cursor.execute("""
                    ALTER TABLE QueryRuns
                    ADD COLUMN total_elapsed_ms FLOAT NULL
                """)

            # Allow missing database-side timings.
            cursor.execute(
                "SHOW COLUMNS FROM QueryRuns LIKE 'duration_ms'"
            )
            duration_column = cursor.fetchone()

            if duration_column and duration_column[2] == "NO":
                cursor.execute("""
                    ALTER TABLE QueryRuns
                    MODIFY COLUMN duration_ms FLOAT NULL
                """)

            # Preserve query errors and unavailable measurements separately.
            cursor.execute(
                "SHOW COLUMNS FROM QueryRuns LIKE 'status'"
            )
            status_column = cursor.fetchone()

            if status_column:
                status_type = status_column[1].upper()

                if "'ERROR'" not in status_type or "'UNAVAILABLE'" not in status_type:
                    cursor.execute("""
                        ALTER TABLE QueryRuns
                        MODIFY COLUMN status
                        ENUM('FAST', 'SLOW', 'ERROR', 'UNAVAILABLE')
                        NOT NULL
                    """)

            try:
                cursor.execute(ENABLE_PERFORMANCE_SCHEMA)
            except Exception as pe:
                logger.warning(f"Could not update Performance Schema consumers: {pe}")
                
            conn.commit()
            logger.info("Database schema initialized.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to initialize database: {e}")
            raise e
        finally:
            cursor.close()