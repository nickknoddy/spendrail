"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "spend-rail"
    app_env: str = "development"
    debug: bool = True

    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"

    # Upload Configuration
    upload_dir: str = "uploads"
    max_file_size_mb: int = 10
    allowed_extensions: str = "jpg,jpeg,png,webp,heic,heif"

    # Logging
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    # CORS
    cors_origins: str = "https://i5k43so0zakfco46i9ay.share.dreamflow.app, https://spendrail.web.app, *"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def upload_path(self) -> Path:
        """Get the upload directory as a Path object."""
        return Path(self.upload_dir)

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Get allowed extensions as a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
