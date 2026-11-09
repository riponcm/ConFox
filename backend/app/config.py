"""Settings come from the environment (or a local .env that is never committed).

The OpenTelemetry exporters read OTEL_* straight from os.environ, not from these settings, so the .env files are
loaded into the process environment first. Values already set in the real environment win.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (ROOT / "backend" / ".env", ROOT / ".env")

for _f in ENV_FILES:
    load_dotenv(_f, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    es_url: str = "http://localhost:9200"
    idx_sessions: str = "confox-sessions"

    service_name: str = "confox-api"
    deployment_environment: str = "hackathon"

    # Lets the demo trigger a real failure for Dash0 to find. Off unless set in .env.
    enable_debug_endpoints: bool = False


settings = Settings()
