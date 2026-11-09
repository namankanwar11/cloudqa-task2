from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    ai_provider: Literal["openai", "groq"] = "openai"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
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
    @property
    def active_key(self):
        return self.groq_api_key if self.ai_provider == "groq" else self.openai_api_key

    @property
    def active_model(self):
        return self.groq_model if self.ai_provider == "groq" else self.openai_model

    @property
    def key_variable(self):
        return "GROQ_API_KEY" if self.ai_provider == "groq" else "OPENAI_API_KEY"