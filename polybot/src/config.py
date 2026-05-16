"""
Application configuration.

All settings are loaded from environment variables with sensible defaults
for local development. No hardcoded secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class Environment(Enum):
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection settings."""

    url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///polybot.db"
        )
    )


@dataclass(frozen=True)
class IngestionConfig:
    """Settings for data ingestion from Polymarket APIs."""

    # API base URLs
    gamma_api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "GAMMA_API_BASE_URL", "https://gamma-api.polymarket.com"
        )
    )
    data_api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DATA_API_BASE_URL", "https://data-api.polymarket.com"
        )
    )
    clob_api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "CLOB_API_BASE_URL", "https://clob.polymarket.com"
        )
    )

    # Rate limiting — CLOB API is permissive; 10/s is safe for local dev.
    # Throttle down in cloud config if doing large-scale fetches.
    max_requests_per_second: float = field(
        default_factory=lambda: float(
            os.getenv("MAX_REQUESTS_PER_SECOND", "10.0")
        )
    )

    # Retry settings
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )
    retry_backoff_base: float = field(
        default_factory=lambda: float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))
    )

    # Batch sizes
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("INGESTION_BATCH_SIZE", "100"))
    )

    # Local mode fetches limited data for fast iteration
    local_market_limit: int = field(
        default_factory=lambda: int(os.getenv("LOCAL_MARKET_LIMIT", "10"))
    )


@dataclass(frozen=True)
class AppConfig:
    """Top-level application config."""

    environment: Environment = field(
        default_factory=lambda: Environment(
            os.getenv("ENVIRONMENT", "local")
        )
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "DEBUG")
    )
    random_seed: int = field(
        default_factory=lambda: int(os.getenv("RANDOM_SEED", "42"))
    )

    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)

    @property
    def is_local(self) -> bool:
        return self.environment == Environment.LOCAL
