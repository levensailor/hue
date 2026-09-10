"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Names and paths come from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Hue Session")
    app_author: str = Field(default="levensailor")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8742)
    app_device_name: str = Field(default="mac")

    log_dir: str = Field(default="logs")
    log_file_name: str = Field(default="hue-session.log")
    log_max_bytes: int = Field(default=1_048_576)
    log_backup_count: int = Field(default=3)
    log_level: str = Field(default="INFO")

    data_dir: str = Field(default="data")
    settings_file_name: str = Field(default="settings.json")
    credentials_file_name: str = Field(default="credentials.json")

    hue_discovery_url: str = Field(default="https://discovery.meethue.com/")
    hue_discovery_timeout_seconds: float = Field(default=4.0)
    hue_mdns_timeout_seconds: float = Field(default=5.0)
    hue_pair_device_type: str = Field(default="hue-session#mac")
    hue_stream_idle_timeout_seconds: float = Field(default=60.0)
    hue_stream_hz: float = Field(default=40.0)

    audio_block_size: int = Field(default=2048)
    audio_preferred_sample_rate: int = Field(default=48000)
    audio_ssl_name_hints: str = Field(default="SSL,Solid State Logic")

    show_default_mode: str = Field(default="spectrum")
    show_default_sensitivity: float = Field(default=1.0)
    show_default_brightness: float = Field(default=0.85)
    show_default_saturation: float = Field(default=0.95)

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def log_path(self) -> Path:
        return self.project_root / self.log_dir / self.log_file_name

    @property
    def data_path(self) -> Path:
        return self.project_root / self.data_dir

    @property
    def settings_path(self) -> Path:
        return self.data_path / self.settings_file_name

    @property
    def credentials_path(self) -> Path:
        return self.data_path / self.credentials_file_name

    @property
    def static_path(self) -> Path:
        return Path(__file__).resolve().parent / "static"

    @property
    def ssl_name_hints(self) -> list[str]:
        return [hint.strip() for hint in self.audio_ssl_name_hints.split(",") if hint.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
