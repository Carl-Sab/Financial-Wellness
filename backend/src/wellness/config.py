from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path so `.env` loads regardless of the process's working directory
# (e.g. running scripts/ from a different cwd than the FastAPI app).
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"

    postgres_user: str = "wellness"
    postgres_password: str = "wellness"
    postgres_db: str = "wellness"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"

    # Optional: enables the in-app relationship summary's AI wording and the
    # standalone correlation report. Left optional so importing wellness.db —
    # which builds the engine at module load time — doesn't fail for every
    # other use of this app just because this one key isn't set yet.
    gateway_api_key: str | None = Field(default=None, validation_alias="API_KEY_SECRET_FROM_EURISKO")
    report_model: str = "claude-sonnet-5"

    # No default, deliberately: a fallback here (even an obvious placeholder
    # like "dev-secret") is exactly how a real secret fails to get set in
    # production and nobody notices until it's a signing key an attacker can
    # guess. Missing JWT_SECRET must fail app startup, not degrade quietly —
    # see security.py's create_access_token/decode_access_token.
    jwt_secret: str
    # Not a secret — just where CORS/cookies expect the dev frontend to be.
    # Real default is fine here.
    frontend_origin: str = "http://localhost:5173"

    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
