import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    QueryShark Application Settings and Environment Configuration.
    Loads configurations from environment variables or .env file with safe defaults.
    """
    PROJECT_NAME: str = "QueryShark"
    API_V1_STR: str = "/api/v1"
    
    # MySQL Database Connection Details
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "shreyansh"
    MYSQL_DATABASE: str = "queryshark_db"
    
    # Query Profiling & Thresholding
    SLOW_QUERY_THRESHOLD_MS: float = 100.0
    DB_POOL_NAME: str = "queryshark_pool"
    DB_POOL_SIZE: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()