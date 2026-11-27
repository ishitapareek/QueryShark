import logging
import threading
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
        db_path=None
    ):
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500.")

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

        self._closed = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._worker = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="QuerySharkTelemetryWorker"
        )
        self._worker.start()

    def send_telemetry(self, record):
        with self._lock:
            if self._closed:
                logger.warning("Client is closed. Telemetry rejected.")
                return False

            try:
                # Generate the ID once, before saving to SQLite.
                # It remains the same across retries and restarts.
                record = dict(record)
                record.setdefault("event_id", str(uuid.uuid4()))

                return self.storage.enqueue(record)

            except Exception:
                logger.exception("Could not persist telemetry.")
                return False

    def send_telemetry_batch(self, records):
        """Persist multiple records in one SQLite transaction."""

        with self._lock:
            if self._closed:
                logger.warning("Client is closed. Telemetry rejected.")
                return 0

            try:
                prepared_records = []

                for record in records:
                    item = dict(record)
                    item.setdefault("event_id", str(uuid.uuid4()))
                    prepared_records.append(item)

                return self.storage.enqueue_many(prepared_records)

            except Exception:
                logger.exception("Could not persist telemetry batch.")
                return 0

    def _send_batch_with_retries(self, records):
        local_ids = [item["id"] for item in records]

        expected_event_ids = {
            item["record"]["event_id"] for item in records
        }

        payload = {
            "records": [item["record"] for item in records]
        }

        for attempt in range(self.max_retries + 1):
            if self._stop_event.is_set():
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

                # Only delete local records if the backend confirms
                # receipt of every event in this batch.
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

            if self._stop_event.wait(delay):
                return False

        return False

    def _process_queue(self):
        while not self._stop_event.is_set():
            try:
                records = self.storage.get_batch(
                    batch_size=self.batch_size
                )

                if not records:
                    self._stop_event.wait(0.5)
                    continue

                delivered = self._send_batch_with_retries(records)

                # If delivery failed, leave the records in SQLite.
                # Avoid repeatedly retrying the same batch immediately.
                if not delivered:
                    self._stop_event.wait(2)

            except Exception:
                logger.exception("Error while processing telemetry queue.")
                self._stop_event.wait(2)

    def pending_count(self):
        return self.storage.pending_count()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True

        self._stop_event.set()
        self._worker.join()

        logger.info(
            "QueryShark stopped. %s records remain pending.",
            self.pending_count()
        )
