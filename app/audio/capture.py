"""Live input capture from an SSL (or any Core Audio) interface."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

import numpy as np
import sounddevice as sd

from app.config import Settings

LOGGER = logging.getLogger(__name__)


class AudioCapture:
    """Non-blocking input stream that keeps the latest analyzed-size block."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._stream: sd.InputStream | None = None
        self._sample_rate = settings.audio_preferred_sample_rate
        self._channels = 2

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    def start(self, device_index: int, channel_map: list[int]) -> None:
        self.stop()
        device_info = sd.query_devices(device_index, "input")
        max_channels = int(device_info.get("max_input_channels") or 1)
        selected = [index for index in channel_map if 0 <= index < max_channels]
        if not selected:
            selected = [0]
        self._channels = len(selected)
        self._sample_rate = int(
            device_info.get("default_samplerate") or self._settings.audio_preferred_sample_rate
        )
        extra_settings = self._core_audio_map(selected)
        LOGGER.info(
            "Opening input device %s (%s) channels=%s rate=%s",
            device_index,
            device_info.get("name"),
            selected,
            self._sample_rate,
        )
        self._stream = sd.InputStream(
            device=device_index,
            channels=self._channels,
            samplerate=self._sample_rate,
            blocksize=self._settings.audio_block_size,
            dtype="float32",
            extra_settings=extra_settings,
            callback=self._callback,
        )
        self._stream.start()

    def read_latest(self) -> np.ndarray | None:
        with self._lock:
            if self._latest is None:
                return None
            return self._latest.copy()

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            LOGGER.exception("Error while closing audio stream")
        self._stream = None
        with self._lock:
            self._latest = None
        LOGGER.info("Audio capture stopped")

    def _callback(self, indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        if status:
            LOGGER.warning("Audio status: %s", status)
        with self._lock:
            self._latest = np.array(indata, dtype=np.float32, copy=True)

    def _core_audio_map(self, channel_map: list[int]) -> Any:
        if sys.platform != "darwin":
            return None
        if channel_map == list(range(len(channel_map))):
            return None
        try:
            return sd.CoreAudioSettings(channel_map=channel_map)
        except Exception:
            LOGGER.exception("Core Audio channel map failed; using first %s channels", len(channel_map))
            return None
