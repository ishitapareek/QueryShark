import logging
from contextlib import contextmanager
from mysql.connector import pooling, Error
from app.core.config import settings

logger = logging.getLogger(__name__)

class DatabasePool:
    _pool = None

    @classmethod
    def initialize(cls):
        if cls._pool is None:
            try:
                cls._pool = pooling.MySQLConnectionPool(
                    pool_name=settings.DB_POOL_NAME,
                    pool_size=settings.DB_POOL_SIZE,
                    pool_reset_session=True,
                    host=settings.MYSQL_HOST,
                    port=settings.MYSQL_PORT,
                    user=settings.MYSQL_USER,
                    password=settings.MYSQL_PASSWORD,
                    database=settings.MYSQL_DATABASE
                )
                logger.info("MySQL Connection Pool initialized successfully.")
            except Error as e:
                logger.error(f"Error initializing MySQL Connection Pool: {e}")
                raise e

    @classmethod
    @contextmanager
    def get_connection(cls):
        if cls._pool is None:
            cls.initialize()
        connection = cls._pool.get_connection()
        try:
            yield connection
        finally:
            connection.close()
            
# not currently used
def get_db():
    with DatabasePool.get_connection() as conn:
        yield conn