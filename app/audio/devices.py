"""Enumerate Core Audio input devices, preferring SSL interfaces."""

from __future__ import annotations

import logging

import sounddevice as sd

from app.config import Settings
from app.models import AudioDevice, AudioDevicesResponse

LOGGER = logging.getLogger(__name__)


def list_input_devices(settings: Settings) -> AudioDevicesResponse:
    """Return every PortAudio input device with SSL hints flagged."""
    raw_devices = sd.query_devices()
    host_apis = sd.query_hostapis()
    default_index = _default_input_index()
    devices: list[AudioDevice] = []

    for index, device in enumerate(raw_devices):
        max_inputs = int(device.get("max_input_channels") or 0)
        if max_inputs < 1:
            continue
        name = str(device.get("name") or f"Device {index}")
        host_api_index = int(device.get("hostapi") or 0)
        host_api_name = str(host_apis[host_api_index].get("name") or "unknown")
        devices.append(
            AudioDevice(
                index=index,
                name=name,
                host_api=host_api_name,
                max_input_channels=max_inputs,
                default_samplerate=float(device.get("default_samplerate") or 0),
                is_ssl=_matches_ssl(name, settings),
                is_default=index == default_index,
            )
        )

    LOGGER.info("Found %s input devices", len(devices))
    return AudioDevicesResponse(devices=devices, default_index=default_index)


def _default_input_index() -> int | None:
    default = sd.default.device
    if isinstance(default, (list, tuple)) and default:
        value = default[0]
        return int(value) if value is not None and int(value) >= 0 else None
    return None


def _matches_ssl(name: str, settings: Settings) -> bool:
    lowered = name.lower()
    return any(hint.lower() in lowered for hint in settings.ssl_name_hints)
