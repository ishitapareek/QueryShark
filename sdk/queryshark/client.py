
import logging
import queue
import threading

import requests


logger = logging.getLogger(__name__)


class QuerySharkClient:
    """
    Sends captured query telemetry to the QueryShark backend
    using a background worker.
    """

    def __init__(
        self,
        agent_url="http://127.0.0.1:8000",
        queue_size=1000
    ):
        self.telemetry_url = (
            agent_url.rstrip("/") + "/api/v1/queries/telemetry"
        )

        self._queue = queue.Queue(maxsize=queue_size)
        self._closed = False

        self._worker = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="QuerySharkTelemetryWorker"
        )

        self._worker.start()

    def send_telemetry(self, record):
        """
        Add telemetry to the queue without waiting for HTTP.
        This method is called by the query interceptor.
        """

        if self._closed:
            return

        try:
            self._queue.put_nowait(record)

        except queue.Full:
            logger.warning(
                "QueryShark telemetry queue is full. "
                "Dropping telemetry record."
            )

    def _process_queue(self):
        """
        Background worker that sends queued records to QueryShark.
        """

        while True:
            record = self._queue.get()

            try:
                if record is None:
                    return

                response = requests.post(
                    self.telemetry_url,
                    json=record,
                    timeout=3
                )

                response.raise_for_status()

                logger.debug(
                    "QueryShark telemetry sent successfully."
                )

            except requests.RequestException:
                logger.exception(
                    "Could not send telemetry to QueryShark."
                )

            finally:
                self._queue.task_done()

    def close(self):
        """
        Wait for queued telemetry to be processed and stop worker.
        """

        if self._closed:
            return

        self._closed = True

        self._queue.join()
        self._queue.put(None)

        self._worker.join()
