"""Settings come from the environment (or a local .env that is never committed)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    es_url: str = "http://localhost:9200"


settings = Settings()
