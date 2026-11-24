
import logging
import queue
import threading
import time

import requests


logger = logging.getLogger(__name__)


class QuerySharkClient:
    """
    Sends captured query telemetry to the QueryShark backend
    using a bounded queue and background worker.
    """

    def __init__(
        self,
        agent_url="http://127.0.0.1:8000",
        queue_size=1000,
        max_retries=3,
        retry_backoff=1,
        request_timeout=3
    ):
        if queue_size <= 0:
            raise ValueError("queue_size must be greater than 0")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.telemetry_url = (
            agent_url.rstrip("/") + "/api/v1/queries/telemetry"
        )

        self._queue = queue.Queue(maxsize=queue_size)
        self._closed = False
        self._lock = threading.Lock()

        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.request_timeout = request_timeout

        self._worker = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="QuerySharkTelemetryWorker"
        )

        self._worker.start()

    def send_telemetry(self, record):
        """
        Add telemetry to the queue without waiting for HTTP.
        """

        with self._lock:
            if self._closed:
                logger.warning(
                    "QueryShark client is closed. "
                    "Telemetry record was rejected."
                )
                return

            try:
                self._queue.put_nowait(record)

            except queue.Full:
                logger.warning(
                    "QueryShark telemetry queue is full. "
                    "Dropping the newest telemetry record."
                )

    def _send_with_retries(self, record):
        """
        Send one telemetry record, retrying failed requests.
        """

        for attempt in range(self.max_retries + 1):

            try:
                response = requests.post(
                    self.telemetry_url,
                    json=record,
                    timeout=self.request_timeout
                )

                response.raise_for_status()

                logger.debug(
                    "QueryShark telemetry sent successfully."
                )

                return True

            except requests.RequestException:

                if attempt == self.max_retries:
                    logger.exception(
                        "Telemetry delivery failed after %s attempts.",
                        attempt + 1
                    )
                    return False

                delay = self.retry_backoff * (2 ** attempt)

                logger.warning(
                    "Telemetry delivery failed. "
                    "Retrying in %s seconds (attempt %s of %s).",
                    delay,
                    attempt + 1,
                    self.max_retries + 1
                )

                time.sleep(delay)

            except Exception:
                logger.exception(
                    "Unexpected error while sending telemetry."
                )
                return False

        return False

    def _process_queue(self):
        """
        Background worker that processes queued telemetry.
        """

        while True:
            record = self._queue.get()

            try:
                if record is None:
                    return

                self._send_with_retries(record)

            except Exception:
                logger.exception(
                    "Unexpected error in telemetry worker."
                )

            finally:
                self._queue.task_done()

    def close(self):
        """
        Process pending records and safely stop the worker.
        """

        with self._lock:
            if self._closed:
                return

            self._closed = True

        # Wait until all queued records have been attempted.
        self._queue.join()

        # Send shutdown signal to the worker.
        self._queue.put(None)

        self._worker.join()

        logger.info("QueryShark telemetry worker stopped.")
