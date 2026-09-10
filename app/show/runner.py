"""Background loop: capture → analyze → stream Hue frames → notify UI."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.audio.analyzer import AnalysisFrame, AudioAnalyzer
from app.audio.capture import AudioCapture
from app.config import Settings
from app.hue.bridge import HueController
from app.models import HueChannel, ShowMode, ShowStartRequest, ShowStatus
from app.show.engine import ShowEngine

LOGGER = logging.getLogger(__name__)

MeterCallback = Callable[[dict], Awaitable[None]]


class ShowRunner:
    """Owns the live lightshow task."""

    def __init__(
        self,
        settings: Settings,
        hue: HueController,
        on_meter: MeterCallback,
    ) -> None:
        self._settings = settings
        self._hue = hue
        self._on_meter = on_meter
        self._capture = AudioCapture(settings)
        self._engine = ShowEngine()
        self._task: asyncio.Task[None] | None = None
        self._status = ShowStatus(running=False)
        self._channels: list[HueChannel] = []
        self._request: ShowStartRequest | None = None

    @property
    def status(self) -> ShowStatus:
        return self._status

    async def start(self, request: ShowStartRequest, channels: list[HueChannel]) -> ShowStatus:
        if not channels:
            raise ValueError("Entertainment area has no channels")
        await self.stop()
        self._request = request
        self._channels = channels
        self._capture.start(request.audio_device_index, request.channel_map)
        await self._hue.start_stream(request.area_id)
        self._status = ShowStatus(
            running=True,
            mode=request.mode,
            area_id=request.area_id,
            audio_device_index=request.audio_device_index,
            message="Lightshow running",
        )
        self._task = asyncio.create_task(self._loop(), name="hue-session-show")
        LOGGER.info("Show started mode=%s area=%s", request.mode, request.area_id)
        return self._status

    async def stop(self) -> ShowStatus:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._capture.stop()
        await self._hue.stop_stream()
        self._status = ShowStatus(running=False, message="Lightshow stopped")
        return self._status

    async def _loop(self) -> None:
        request = self._request
        if request is None:
            return
        analyzer = AudioAnalyzer(
            sample_rate=self._capture.sample_rate,
            sensitivity=request.sensitivity,
        )
        interval = 1.0 / max(10.0, self._settings.hue_stream_hz)
        try:
            while True:
                block = self._capture.read_latest()
                if block is None:
                    await asyncio.sleep(interval)
                    continue
                frame = analyzer.analyze(block)
                commands = self._engine.colors(
                    frame,
                    self._channels,
                    request.mode,
                    request.brightness,
                    request.saturation,
                )
                self._hue.send_colors(commands)
                await self._on_meter(self._meter_payload(frame, request.mode))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Show loop crashed")
            self._status = ShowStatus(running=False, message="Lightshow stopped after an error")
            self._capture.stop()
            await self._hue.stop_stream()

    def _meter_payload(self, frame: AnalysisFrame, mode: ShowMode) -> dict:
        request = self._request
        brightness = request.brightness if request else 1.0
        saturation = request.saturation if request else 1.0
        return {
            "rms": frame.rms,
            "bass": frame.bass,
            "mid": frame.mid,
            "high": frame.high,
            "centroid": frame.centroid,
            "beat": frame.beat,
            "bands": frame.bands,
            "channel_energy": frame.channel_energy,
            "lights": self._engine.preview(
                frame,
                self._channels,
                mode,
                brightness,
                saturation,
            ),
        }
