# app/settings.py
from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,  # Immutable settings for thread safety
    )

    # API URLs (base URLs without query parameters)
    nordvpn_api_url: str = "https://api.nordvpn.com/v1/servers"
    surfshark_api_url: str = "https://api.surfshark.com/v3/server/clusters"

    # Cache settings
    cache_ttl: Annotated[int, Field(ge=60, le=3600)] = 300

    # HTTP Client settings
    http_timeout: Annotated[float, Field(ge=5.0, le=120.0)] = 30.0
    http_max_connections: Annotated[int, Field(ge=10, le=500)] = 100
    http_max_keepalive_connections: Annotated[int, Field(ge=5, le=100)] = 20

    # API Limits (0 = unlimited / fetch all)
    nordvpn_server_limit: Annotated[int, Field(ge=0, le=10000)] = 0
    default_page_size: Annotated[int, Field(ge=10, le=500)] = 100
    max_page_size: Annotated[int, Field(ge=100, le=2000)] = 1000

    # Security settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    cors_allow_credentials: bool = True
    api_keys: List[str] = []
    enable_api_key_auth: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: Annotated[int, Field(ge=10, le=10000)] = 100
    rate_limit_period: Annotated[int, Field(ge=10, le=3600)] = 60

    # Security headers
    enable_security_headers: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"

    # Application settings
    app_name: str = "VPN API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Trusted proxies for X-Forwarded-For handling
    trusted_hosts: List[str] = ["127.0.0.1", "::1"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """Ensure no wildcard CORS in production-like settings."""
        if "*" in v:
            raise ValueError("Wildcard CORS origin '*' is not allowed for security")
        return v

    @field_validator("api_keys", mode="before")
    @classmethod
    def validate_api_keys(cls, v: List[str]) -> List[str]:
        """Validate API key minimum length."""
        for key in v:
            if len(key) < 32:
                raise ValueError("API keys must be at least 32 characters")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance for performance."""
    return Settings()


settings = get_settings()
