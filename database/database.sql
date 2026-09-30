CREATE DATABASE QueryShark;
USE QueryShark;

CREATE TABLE QueryRuns (
    queryID INT AUTO_INCREMENT PRIMARY KEY,
    sql_text TEXT NOT NULL,
    current_schema VARCHAR(100) NOT NULL,
    duration_ms FLOAT NOT NULL,
    status ENUM('FAST', 'SLOW') NOT NULL
);

DESCRIBE QueryRuns;

SELECT * FROM QueryRuns;

SHOW TABLES FROM performance_schema
LIKE 'events_statements_%';

DESCRIBE performance_schema.events_statements_history;



SELECT e.SQL_TEXT,
                e.CURRENT_SCHEMA,
                e.TIMER_WAIT / 1000000000 AS duration_ms
            FROM performance_schema.events_statements_history e
            ORDER BY e.EVENT_ID DESC;
            