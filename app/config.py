"""Konfiguration ueber Umgebungsvariablen (Prefix ADSB_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADSB_", env_file=".env", extra="ignore")

    provider: str = "adsblol"
    api_key: str = ""
    token: str = "changeme"

    cache_ttl: float = 8.0
    min_upstream_interval: float = 1.0
    upstream_timeout: float = 6.0
    max_targets: int = 20

    log_level: str = "INFO"


settings = Settings()
