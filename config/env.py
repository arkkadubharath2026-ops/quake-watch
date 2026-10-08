"""Typed, validated application configuration loaded from environment / .env.

All runtime configuration flows through :class:`AppSettings`; Django settings and
non-Django modules read from here instead of ``os.environ`` directly.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QW_",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = Environment.DEVELOPMENT
    secret_key: SecretStr
    debug: bool = False
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["localhost"])
    csrf_trusted_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    app_version: str = "dev"
    # Reverse proxies in front of the app that append to X-Forwarded-For (0 = direct exposure).
    num_proxies: int = Field(default=0, ge=0, le=5)

    arango_url: str = "http://127.0.0.1:8529"
    arango_db: str = "quakewatch"
    arango_user: str = "root"
    arango_password: SecretStr
    arango_request_timeout: float = Field(default=30.0, gt=0)

    usgs_base_url: str = "https://earthquake.usgs.gov"
    sync_feed: str = "all_day"
    sync_interval_seconds: int = Field(default=300, ge=60)
    http_connect_timeout: float = Field(default=5.0, gt=0)
    http_read_timeout: float = Field(default=20.0, gt=0)
    http_max_retries: int = Field(default=4, ge=0, le=10)
    circuit_failure_threshold: int = Field(default=5, ge=1)
    circuit_reset_seconds: int = Field(default=300, ge=10)
    freshness_degraded_minutes: int = Field(default=20, ge=1)
    freshness_stale_minutes: int = Field(default=120, ge=1)
    raw_payload_retention_days: int = Field(default=90, ge=1)
    backfill_window_days: int = Field(default=7, ge=1, le=31)

    log_level: str = "INFO"
    log_json: bool = False

    @field_validator("allowed_hosts", "csrf_trusted_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("sync_feed")
    @classmethod
    def _valid_feed(cls, value: str) -> str:
        allowed = {
            f"{level}_{period}"
            for level in ("significant", "4.5", "2.5", "1.0", "all")
            for period in ("hour", "day", "week", "month")
        }
        if value not in allowed:
            raise ValueError(f"sync_feed must be one of {sorted(allowed)}")
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> AppSettings:
        if self.env is Environment.PRODUCTION:
            if self.debug:
                raise ValueError("QW_DEBUG must be false in production")
            if len(self.secret_key.get_secret_value()) < 50:
                raise ValueError("QW_SECRET_KEY must be at least 50 characters in production")
        if self.freshness_stale_minutes <= self.freshness_degraded_minutes:
            raise ValueError("freshness_stale_minutes must exceed freshness_degraded_minutes")
        return self

    @property
    def resolved_app_version(self) -> str:
        """Explicit QW_APP_VERSION (container builds) or the checkout's git SHA."""
        if self.app_version != "dev":
            return self.app_version
        sha = detect_git_sha()
        return f"git-{sha}" if sha else "dev"

    @property
    def arango_database_name(self) -> str:
        """Tests always run against an isolated ``<db>_test`` database."""
        if self.env is Environment.TEST and not self.arango_db.endswith("_test"):
            return f"{self.arango_db}_test"
        return self.arango_db


def detect_git_sha(root: Path = BASE_DIR) -> str | None:
    """Short commit SHA from ``.git`` files (no subprocess); None outside a git checkout."""
    head = root / ".git" / "HEAD"
    try:
        content = head.read_text(encoding="utf-8").strip()
        if content.startswith("ref: "):
            ref = content.removeprefix("ref: ")
            ref_file = root / ".git" / ref
            if ref_file.exists():
                return ref_file.read_text(encoding="utf-8").strip()[:12]
            packed = root / ".git" / "packed-refs"
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0][:12]
            return None
        return content[:12]
    except OSError:
        return None


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]  # values come from the environment
