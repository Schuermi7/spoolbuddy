from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server
    host: str = "0.0.0.0"
    port: int = 3000

    # Database
    database_path: Path = Path("spoolbuddy.db")

    # Static files (frontend)
    static_dir: Path = Path("../frontend/dist")

    class Config:
        env_prefix = "SPOOLBUDDY_"


settings = Settings()
