
import json
import logging
import sqlite3

from pathlib import Path


logger = logging.getLogger(__name__)


class SQLiteTelemetryQueue:
    """
    Persistent local storage for pending QueryShark telemetry.
    """

    def __init__(
        self,
        db_path=None,
        max_records=100000
    ):
        if max_records <= 0:
            raise ValueError("max_records must be greater than 0")

        if db_path is None:
            db_path = (
                Path.home()
                / ".queryshark"
                / "telemetry.db"
            )

        self.db_path = Path(db_path)
        self.max_records = max_records

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self._initialize_database()

    def _connect(self):
        connection = sqlite3.connect(
            self.db_path,
            timeout=10
        )

        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA busy_timeout = 10000")

        return connection

    def _initialize_database(self):
        connection = self._connect()

        try:
            connection.execute("PRAGMA journal_mode = WAL")

            connection.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT
                )
            """)

            connection.commit()

            logger.info("SQLite telemetry queue initialized.")

        finally:
            connection.close()

    def enqueue(self, record):
        """
        Store one telemetry record.

        Returns:
            True if stored successfully.
            False if the queue is full.
        """

        payload = json.dumps(record)

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            result = connection.execute("""
                SELECT COUNT(*) AS total
                FROM telemetry_queue
            """)

            current_count = result.fetchone()["total"]

            if current_count >= self.max_records:
                connection.rollback()

                logger.warning(
                    "SQLite telemetry queue is full. "
                    "New record rejected."
                )

                return False

            connection.execute("""
                INSERT INTO telemetry_queue (payload)
                VALUES (?)
            """, (payload,))

            connection.commit()

            return True

        except Exception:
            connection.rollback()
            logger.exception("Could not store telemetry record.")
            raise

        finally:
            connection.close()


    def enqueue_many(self, records):
        """
        Store multiple telemetry records in one SQLite transaction.

        Returns:
            Number of records successfully stored.
        """

        if not records:
            return 0

        # Serialize records before opening the transaction.
        payloads = [
            (json.dumps(record),)
            for record in records
        ]

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            result = connection.execute("""
                SELECT COUNT(*) AS total
                FROM telemetry_queue
            """)

            current_count = result.fetchone()["total"]
            available_slots = self.max_records - current_count

            if available_slots <= 0:
                connection.rollback()

                logger.warning(
                    "SQLite telemetry queue is full. "
                    "No records were stored."
                )
                return 0

            accepted_payloads = payloads[:available_slots]

            connection.executemany("""
                INSERT INTO telemetry_queue (payload)
                VALUES (?)
            """, accepted_payloads)

            connection.commit()

            accepted_count = len(accepted_payloads)

            if accepted_count < len(records):
                logger.warning(
                    "Queue capacity reached. Stored %s of %s records.",
                    accepted_count,
                    len(records)
                )

            return accepted_count

        except Exception:
            connection.rollback()
            logger.exception("Could not store telemetry batch.")
            raise

        finally:
            connection.close()

    def get_batch(self, batch_size=100):
        """
        Retrieve the oldest pending records.
        Does not delete them.
        """

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")

        connection = self._connect()

        try:
            rows = connection.execute("""
                SELECT id, payload, attempts
                FROM telemetry_queue
                ORDER BY id ASC
                LIMIT ?
            """, (batch_size,)).fetchall()

            return [
                {
                    "id": row["id"],
                    "record": json.loads(row["payload"]),
                    "attempts": row["attempts"]
                }
                for row in rows
            ]

        finally:
            connection.close()

    def acknowledge(self, record_ids):
        """
        Delete records after successful delivery.
        """

        if not record_ids:
            return

        connection = self._connect()

        try:
            connection.executemany("""
                DELETE FROM telemetry_queue
                WHERE id = ?
            """, [(record_id,) for record_id in record_ids])

            connection.commit()

        finally:
            connection.close()

    def mark_failed(self, record_ids, error_message):
        """
        Increment attempts and store the latest delivery error.
        Records remain in the queue.
        """

        if not record_ids:
            return

        connection = self._connect()

        try:
            connection.executemany("""
                UPDATE telemetry_queue
                SET attempts = attempts + 1,
                    last_error = ?
                WHERE id = ?
            """, [
                (str(error_message), record_id)
                for record_id in record_ids
            ])

            connection.commit()

        finally:
            connection.close()

    def pending_count(self):
        """
        Return the number of records waiting for delivery.
        """

        connection = self._connect()

        try:
            result = connection.execute("""
                SELECT COUNT(*) AS total
                FROM telemetry_queue
            """)

            return result.fetchone()["total"]

        finally:
            connection.close()
