from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TerraPulse"
    version: str = "1.0.0"
    debug: bool = False

    # no default: the app must not boot with a guessable signing key
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    database_url: str = "sqlite:///./terrapulse.db"
    cors_origins: str = "http://localhost:5173"

    data_dir: Path = Path("../data")
    pipeline_mode: str = "mock"
    mock_stage_seconds: float = 0.55
    max_body_bytes: int = 10 * 1024 * 1024
    rate_limit_enabled: bool = True

    seed_viewer_password: str = "viewer"
    seed_analyst_password: str = "analyst"
    seed_authority_password: str = "officer"

    sentinel_client_id: str = ""
    sentinel_client_secret: str = ""

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def scenes_dir(self) -> Path:
        return self.data_dir / "scenes"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def env_dir(self) -> Path:
        return self.data_dir / "env"


@lru_cache
def settings() -> Settings:
    return Settings()
