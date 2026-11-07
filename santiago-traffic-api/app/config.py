from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tomtom_api_key: SecretStr = SecretStr("")
    tomtom_timeout_seconds: float = Field(default=10, gt=0, le=60, allow_inf_nan=False)
    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("tomtom_api_key", mode="before")
    @classmethod
    def strip_api_key(cls, value: str | SecretStr) -> str:
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        return raw.strip()

    @property
    def tomtom_configured(self) -> bool:
        return bool(self.tomtom_api_key.get_secret_value())
