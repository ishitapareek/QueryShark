
import logging

from app.core.config import settings
from app.db.connection import DatabasePool

logger = logging.getLogger(__name__)


def cleanup_expired_records() -> int:
    """
    Delete QueryRuns records older than the configured
    retention period, in manageable batches.

    Returns the total number of deleted records.
    """

    total_deleted = 0

    try:
        with DatabasePool.get_connection() as conn:
            cursor = conn.cursor()

            while True:
                cursor.execute(
                    """
                    DELETE FROM QueryRuns
                    WHERE timestamp < DATE_SUB(
                        NOW(), INTERVAL %s DAY
                    )
                    ORDER BY timestamp ASC
                    LIMIT %s
                    """,
                    (
                        settings.RETENTION_DAYS,
                        settings.CLEANUP_BATCH_SIZE
                    )
                )

                deleted = cursor.rowcount

                conn.commit()

                total_deleted += deleted

                logger.info(
                    "Deleted %s expired QueryRuns records",
                    deleted
                )

                # No more expired records.
                if deleted < settings.CLEANUP_BATCH_SIZE:
                    break

            cursor.close()

        logger.info(
            "Retention cleanup completed. Total deleted: %s",
            total_deleted
        )

        return total_deleted

    except Exception:
        logger.exception("Retention cleanup failed")
        raise
