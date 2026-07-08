from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "OpsLens AI"
    database_url: str = getenv("DATABASE_URL", "sqlite+pysqlite:///./opslens.db")
    jwt_secret: str = getenv("JWT_SECRET", "opslens-local-dev-secret-change-me")
    demo_mode: bool = getenv("DEMO_MODE", "true").lower() == "true"
    cors_origins: str = getenv("CORS_ORIGINS", "http://localhost:3000")
    sql_row_limit: int = int(getenv("SQL_ROW_LIMIT", "500"))
    sql_timeout_ms: int = int(getenv("SQL_TIMEOUT_MS", "5000"))
    sql_complexity_limit: int = int(getenv("SQL_COMPLEXITY_LIMIT", "14"))
    request_rate_limit: int = int(getenv("REQUEST_RATE_LIMIT", "120"))
    environment: str = getenv("ENVIRONMENT", "development")
    trusted_origins_required: bool = getenv("TRUSTED_ORIGINS_REQUIRED", "true").lower() == "true"
    secure_cookie_required: bool = getenv("SECURE_COOKIE_REQUIRED", "true").lower() == "true"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    def startup_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.is_production and self.database_url.startswith("sqlite"):
            warnings.append("SQLite deterministic demo mode is active; use PostgreSQL for production deployment.")
        if self.demo_mode:
            warnings.append("Synthetic demo mode is active; no external integrations are executed.")
        return warnings

    def validate_startup(self) -> None:
        if not self.is_production:
            return
        failures: list[str] = []
        if self.database_url.startswith("sqlite"):
            failures.append("DATABASE_URL must point to PostgreSQL in production.")
        if self.jwt_secret in {"opslens-local-dev-secret-change-me", "phase2-test-secret"} or len(self.jwt_secret) < 32:
            failures.append("JWT_SECRET must be a strong production secret.")
        if not self.cors_origins or "*" in self.cors_origins:
            failures.append("CORS_ORIGINS must be explicit in production.")
        if self.demo_mode:
            failures.append("DEMO_MODE must be false for production startup.")
        if failures:
            raise RuntimeError("Production startup validation failed: " + " ".join(failures))


settings = Settings()
