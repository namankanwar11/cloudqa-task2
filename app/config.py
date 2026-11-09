from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    max_steps: int = Field(default=25, ge=1, le=100)
    max_replans: int = Field(default=3, ge=0, le=10)
    action_timeout_ms: int = Field(default=5000, ge=100, le=30000)
    run_timeout_seconds: int = Field(default=180, ge=5, le=600)
    api_timeout_seconds: int = Field(default=40, ge=1, le=120)
    capture_screenshots: bool = True
    extra_allowed_hosts: str = ""
    allow_localhost: bool = False
    artifacts_dir: Path = ROOT / "artifacts"