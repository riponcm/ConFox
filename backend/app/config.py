"""Settings come from the environment (or a local .env that is never committed).

The OpenTelemetry exporters read OTEL_* straight from os.environ, not from these settings, so the .env files are
loaded into the process environment first. Values already set in the real environment win.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
RAW_SCHEDULE = ROOT / "data" / "raw" / "sessionize-kubecon-na-2026.json"
ENV_FILES = (ROOT / "backend" / ".env", ROOT / ".env")

for _f in ENV_FILES:
    load_dotenv(_f, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    es_url: str = "http://localhost:9200"
    idx_sessions: str = "confox-sessions"
    idx_people: str = "confox-people"
    idx_agenda: str = "confox-agenda"
    idx_transcripts: str = "confox-transcripts"
    idx_activity: str = "confox-activity"
    idx_groups: str = "confox-groups"

    # The demo runs on Emma's Monday morning. Leave DEMO_NOW empty to use the real clock in Salt Lake City.
    demo_now: str = "2026-11-09T08:40:00"
    demo_user: str = "emma"

    # Server-side keys only; never exposed to the browser.
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-opus-5-5"
    embed_model: str = "text-embedding-3-small"
    embed_dims: int = 1536

    service_name: str = "confox-api"
    deployment_environment: str = "hackathon"

    # Lets the demo trigger a real failure for Dash0 to find. Off unless set in .env.
    enable_debug_endpoints: bool = False


settings = Settings()
