"""Hue Session FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.audio.devices import list_input_devices
from app.config import Settings, get_settings
from app.hue.bridge import HueController
from app.logging_setup import setup_logging
from app.models import (
    AppSettingsPayload,
    AudioDevicesResponse,
    HealthResponse,
    HueAreasResponse,
    HueBridge,
    HueBridgesResponse,
    PairRequest,
    PairResponse,
    ShowStartRequest,
    ShowStatus,
)
from app.show.runner import ShowRunner
from app.store import JsonStore

LOGGER = logging.getLogger(__name__)


class MeterHub:
    """Fan-out live meter frames to connected dashboard sockets."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self._clients.add(socket)

    def disconnect(self, socket: WebSocket) -> None:
        self._clients.discard(socket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for socket in list(self._clients):
            try:
                await socket.send_json(payload)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings)
    store = JsonStore(settings)
    hue = HueController(settings)
    hue.load_credentials(store.load_credentials())
    hub = MeterHub()
    runner = ShowRunner(settings, hue, hub.broadcast)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        LOGGER.info("%s starting on %s:%s", settings.app_name, settings.app_host, settings.app_port)
        yield
        await runner.stop()
        LOGGER.info("%s stopped", settings.app_name)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", app_name=settings.app_name, author=settings.app_author)

    @app.get("/api/audio/devices", response_model=AudioDevicesResponse)
    async def audio_devices() -> AudioDevicesResponse:
        try:
            return list_input_devices(settings)
        except Exception as exc:
            LOGGER.exception("Failed to list audio devices")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/hue/bridges", response_model=HueBridgesResponse)
    async def hue_bridges() -> HueBridgesResponse:
        bridges = await hue.discover()
        saved = store.load_settings()
        if saved.hue_host and all(bridge.host != saved.hue_host for bridge in bridges):
            bridges.append(
                HueBridge(host=saved.hue_host, name="Saved bridge", source="saved")
            )
        return HueBridgesResponse(bridges=bridges)

    @app.post("/api/hue/pair", response_model=PairResponse)
    async def hue_pair(request: PairRequest) -> PairResponse:
        device_type = request.device_type or settings.hue_pair_device_type
        try:
            creds = await hue.pair(request.host, device_type)
        except TimeoutError as exc:
            LOGGER.warning("Hue pairing timed out: %s", exc)
            raise HTTPException(
                status_code=408,
                detail="Press the Hue bridge link button, then try again.",
            ) from exc
        except Exception as exc:
            LOGGER.exception("Hue pairing failed")
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        store.save_credentials(creds)
        saved = store.load_settings()
        saved.hue_host = request.host
        store.save_settings(saved)
        return PairResponse(host=request.host, paired=True, message="Bridge paired. Credentials stored locally.")

    @app.get("/api/hue/areas", response_model=HueAreasResponse)
    async def hue_areas() -> HueAreasResponse:
        if not hue.paired:
            return HueAreasResponse(areas=[], paired=False, host="")
        try:
            areas = await hue.list_areas()
        except Exception as exc:
            LOGGER.exception("Failed to list entertainment areas")
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return HueAreasResponse(areas=areas, paired=True, host=hue.host)

    @app.get("/api/settings", response_model=AppSettingsPayload)
    async def get_saved_settings() -> AppSettingsPayload:
        return store.load_settings()

    @app.put("/api/settings", response_model=AppSettingsPayload)
    async def put_saved_settings(payload: AppSettingsPayload) -> AppSettingsPayload:
        store.save_settings(payload)
        return payload

    @app.get("/api/show/status", response_model=ShowStatus)
    async def show_status() -> ShowStatus:
        return runner.status

    @app.post("/api/show/start", response_model=ShowStatus)
    async def show_start(request: ShowStartRequest) -> ShowStatus:
        if not hue.paired:
            raise HTTPException(status_code=409, detail="Pair the Hue bridge before starting a show.")
        areas = await hue.list_areas()
        match = next((area for area in areas if area.id == request.area_id), None)
        if match is None:
            raise HTTPException(
                status_code=404,
                detail="Entertainment area not found. Create a Sync/Entertainment area in the Hue app that includes your Play lights.",
            )
        saved = AppSettingsPayload(
            audio_device_index=request.audio_device_index,
            channel_map=request.channel_map,
            area_id=request.area_id,
            mode=request.mode,
            sensitivity=request.sensitivity,
            brightness=request.brightness,
            saturation=request.saturation,
            hue_host=hue.host,
        )
        store.save_settings(saved)
        try:
            return await runner.start(request, match.channels)
        except Exception as exc:
            LOGGER.exception("Failed to start lightshow")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/show/stop", response_model=ShowStatus)
    async def show_stop() -> ShowStatus:
        return await runner.stop()

    @app.websocket("/ws/meters")
    async def meters(socket: WebSocket) -> None:
        await hub.connect(socket)
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            hub.disconnect(socket)

    index_path = settings.static_path / "index.html"
    app.mount("/static", StaticFiles(directory=settings.static_path), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(index_path)

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_config=None,
    )
