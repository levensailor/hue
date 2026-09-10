"""Persist settings and Hue credentials on disk."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import Settings
from app.models import AppSettingsPayload

LOGGER = logging.getLogger(__name__)


class JsonStore:
    """Small JSON file helper used for settings and credentials."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._settings.data_path.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> AppSettingsPayload:
        raw = self._read(self._settings.settings_path)
        if not raw:
            return AppSettingsPayload(
                mode=self._settings.show_default_mode,  # type: ignore[arg-type]
                sensitivity=self._settings.show_default_sensitivity,
                brightness=self._settings.show_default_brightness,
                saturation=self._settings.show_default_saturation,
            )
        return AppSettingsPayload.model_validate(raw)

    def save_settings(self, payload: AppSettingsPayload) -> None:
        self._write(self._settings.settings_path, payload.model_dump())

    def load_credentials(self) -> dict[str, str]:
        raw = self._read(self._settings.credentials_path)
        if not raw:
            return {}
        return {str(key): str(value) for key, value in raw.items()}

    def save_credentials(self, payload: dict[str, str]) -> None:
        self._write(self._settings.credentials_path, payload)

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.exception("Failed to read %s", path)
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.info("Wrote %s", path)
