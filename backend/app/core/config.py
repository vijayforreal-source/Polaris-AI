from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from POLARIS-prefixed environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="POLARIS_",
        extra="ignore",
    )

    app_name: str = "POLARIS-AI"
    environment: str = "development"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()

