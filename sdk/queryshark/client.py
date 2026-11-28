
import logging
import queue
import threading
import time
import uuid

import requests

from .storage import SQLiteTelemetryQueue

logger = logging.getLogger(__name__)


class QuerySharkClient:
    def __init__(
        self,
        agent_url="http://127.0.0.1:8000",
        queue_size=100000,
        batch_size=100,
        max_retries=3,
        retry_backoff=1,
        request_timeout=10,
        db_path=None,
        buffer_size=5000,
        flush_interval=0.05
    ):
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500.")

        if buffer_size <= 0:
            raise ValueError("buffer_size must be greater than 0.")

        if flush_interval <= 0:
            raise ValueError("flush_interval must be greater than 0.")

        self.telemetry_url = (
            agent_url.rstrip("/") + "/api/v1/queries/telemetry/batch"
        )

        self.storage = SQLiteTelemetryQueue(
            db_path=db_path,
            max_records=queue_size
        )

        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.request_timeout = request_timeout
        self.flush_interval = flush_interval

        # Incoming records wait here briefly before batch persistence.
        self._buffer = queue.Queue(maxsize=buffer_size)

        self._closed = False
        self._lock = threading.Lock()

        self._writer_stop = threading.Event()
        self._delivery_stop = threading.Event()

        # Thread 1: persist incoming records to SQLite in batches.
        self._writer = threading.Thread(
            target=self._write_buffer,
            daemon=True,
            name="QuerySharkStorageWriter"
        )

        # Thread 2: deliver persisted SQLite batches to the backend.
        self._worker = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="QuerySharkTelemetryWorker"
        )

        self._writer.start()
        self._worker.start()

    def send_telemetry(self, record):
        """
        Add one record to the bounded in-memory buffer.

        Returns False if the client is closed or the buffer is full.
        """

        with self._lock:
            if self._closed:
                logger.warning("Client is closed. Telemetry rejected.")
                return False

            try:
                item = dict(record)
                item.setdefault("event_id", str(uuid.uuid4()))

                self._buffer.put_nowait(item)
                return True

            except queue.Full:
                logger.warning(
                    "QueryShark memory buffer is full. "
                    "New telemetry record rejected."
                )
                return False

            except Exception:
                logger.exception("Could not buffer telemetry.")
                return False

    def send_telemetry_batch(self, records):
        """
        Add multiple records to the in-memory buffer.

        Returns the number of records accepted into the buffer.
        """

        accepted = 0

        with self._lock:
            if self._closed:
                logger.warning("Client is closed. Telemetry rejected.")
                return 0

            for record in records:
                try:
                    item = dict(record)
                    item.setdefault("event_id", str(uuid.uuid4()))

                    self._buffer.put_nowait(item)
                    accepted += 1

                except queue.Full:
                    logger.warning(
                        "Memory buffer full. Accepted %s of %s records.",
                        accepted,
                        len(records)
                    )
                    break

                except Exception:
                    logger.exception("Could not buffer telemetry record.")
                    break

        return accepted

    def _write_buffer(self):
        """
        Collect individual records and persist them to SQLite in batches.

        Records are removed from the in-memory queue only after SQLite
        confirms that they have been stored.
        """

        pending = []

        while not self._writer_stop.is_set() or not self._buffer.empty():

            if not pending:
                try:
                    first = self._buffer.get(timeout=self.flush_interval)
                    pending.append(first)
                except queue.Empty:
                    continue

            # Collect more records until the batch is full or the
            # flush interval expires.
            deadline = time.monotonic() + self.flush_interval

            while len(pending) < self.batch_size:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    break

                try:
                    item = self._buffer.get(timeout=remaining)
                    pending.append(item)
                except queue.Empty:
                    break

            try:
                stored = self.storage.enqueue_many(pending)

                if stored > 0:
                    # Only acknowledge records confirmed in SQLite.
                    for _ in range(stored):
                        self._buffer.task_done()

                    pending = pending[stored:]

                if pending:
                    # SQLite may be at capacity. The delivery worker
                    # should free space; retain these records meanwhile.
                    time.sleep(0.1)

            except Exception:
                logger.exception(
                    "Could not persist telemetry batch. Retrying."
                )
                time.sleep(0.5)

        logger.info("QueryShark storage writer stopped.")

    def _send_batch_with_retries(self, records):
        local_ids = [item["id"] for item in records]

        expected_event_ids = {
            item["record"]["event_id"] for item in records
        }

        payload = {
            "records": [item["record"] for item in records]
        }

        for attempt in range(self.max_retries + 1):
            if self._delivery_stop.is_set():
                return False

            try:
                response = requests.post(
                    self.telemetry_url,
                    json=payload,
                    timeout=self.request_timeout
                )

                response.raise_for_status()

                result = response.json()
                received_event_ids = set(result.get("event_ids", []))

                if received_event_ids != expected_event_ids:
                    raise ValueError(
                        "Backend response did not confirm every event ID."
                    )

                self.storage.acknowledge(local_ids)

                logger.info(
                    "Successfully delivered batch of %s records.",
                    len(records)
                )
                return True

            except requests.RequestException as exc:
                error_message = str(exc)

            except Exception as exc:
                error_message = str(exc)

            if attempt == self.max_retries:
                self.storage.mark_failed(local_ids, error_message)

                logger.error(
                    "Batch of %s records remains in SQLite after %s attempts: %s",
                    len(records),
                    attempt + 1,
                    error_message
                )
                return False

            delay = self.retry_backoff * (2 ** attempt)

            logger.warning(
                "Batch delivery failed. Retrying in %s seconds: %s",
                delay,
                error_message
            )

            if self._delivery_stop.wait(delay):
                return False

        return False

    def _process_queue(self):
        while not self._delivery_stop.is_set():
            try:
                records = self.storage.get_batch(
                    batch_size=self.batch_size
                )

                if not records:
                    self._delivery_stop.wait(0.1)
                    continue

                delivered = self._send_batch_with_retries(records)

                if not delivered:
                    self._delivery_stop.wait(2)

            except Exception:
                logger.exception("Error while processing telemetry queue.")
                self._delivery_stop.wait(2)

        logger.info("QueryShark delivery worker stopped.")

    def pending_count(self):
        """Return records already persisted in SQLite."""
        return self.storage.pending_count()

    def buffered_count(self):
        """Return records still waiting for SQLite persistence."""
        return self._buffer.qsize()

    def close(self, timeout=30):
        """
        Stop accepting telemetry, flush the memory buffer to SQLite,
        and allow the delivery worker time to deliver persisted records.

        Any records still pending in SQLite remain available for the
        next client run.
        """

        with self._lock:
            if self._closed:
                return

            self._closed = True

        # First stop the writer after it has drained its memory buffer.
        self._writer_stop.set()
        self._writer.join(timeout=timeout)

        if self._writer.is_alive():
            logger.error(
                "Storage writer did not finish within %s seconds. "
                "%s records may still be buffered in memory.",
                timeout,
                self.buffered_count()
            )

        # Then give the delivery worker time to empty SQLite.
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if not self._writer.is_alive() and self.pending_count() == 0:
                break

            time.sleep(0.1)

        self._delivery_stop.set()
        self._worker.join(timeout=5)

        logger.info(
            "QueryShark stopped. SQLite pending: %s; memory buffered: %s",
            self.pending_count(),
            self.buffered_count()
        )
