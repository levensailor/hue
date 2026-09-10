"""Hue bridge discovery, pairing, area listing, and Entertainment streaming."""

from __future__ import annotations

import inspect
import logging
from typing import Any

import aiohttp
from hue_entertainment import (
    EntertainmentArea,
    EntertainmentSession,
    HueEntertainmentAPI,
    LightColorCommand,
    discover_bridges,
)

from app.config import Settings
from app.models import HueArea, HueBridge, HueChannel

LOGGER = logging.getLogger(__name__)


class HueController:
    """Owns pairing credentials and the live EntertainmentSession."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: EntertainmentSession | None = None
        self._active_area_id = ""
        self.host = ""
        self.username = ""
        self.client_key = ""

    @property
    def paired(self) -> bool:
        return bool(self.host and self.username and self.client_key)

    def load_credentials(self, payload: dict[str, str]) -> None:
        self.host = payload.get("host", "")
        self.username = payload.get("username", "")
        self.client_key = payload.get("clientkey", "")
        if self.paired:
            LOGGER.info("Loaded Hue credentials for host %s", self.host)

    def credentials_payload(self) -> dict[str, str]:
        return {
            "host": self.host,
            "username": self.username,
            "clientkey": self.client_key,
        }

    async def discover(self) -> list[HueBridge]:
        found: dict[str, HueBridge] = {}
        await self._discover_mdns(found)
        await self._discover_cloud(found)
        bridges = list(found.values())
        LOGGER.info("Discovered %s Hue bridge(s)", len(bridges))
        return bridges

    async def pair(self, host: str, device_type: str) -> dict[str, str]:
        LOGGER.info("Pairing with Hue bridge at %s", host)
        api = HueEntertainmentAPI(host)
        try:
            creds = await api.pair(device_type=device_type)
        finally:
            await api.close()
        if "username" not in creds or "clientkey" not in creds:
            raise ValueError(f"Unexpected pairing payload keys: {sorted(creds)}")
        self.host = host
        self.username = creds["username"]
        self.client_key = creds["clientkey"]
        LOGGER.info("Paired with Hue bridge at %s", host)
        return self.credentials_payload()

    async def list_areas(self) -> list[HueArea]:
        if not self.paired:
            return []
        api = HueEntertainmentAPI(self.host, self.username)
        try:
            areas = await api.get_entertainment_areas()
        finally:
            await api.close()
        return [_serialize_area(area) for area in areas]

    async def start_stream(self, area_id: str) -> None:
        if not self.paired:
            raise RuntimeError("Hue bridge is not paired")
        await self.stop_stream()
        session = EntertainmentSession(
            self.host,
            self.username,
            self.client_key,
            idle_timeout=self._settings.hue_stream_idle_timeout_seconds,
        )
        await session.start(area_id)
        self._session = session
        self._active_area_id = area_id
        LOGGER.info("Entertainment stream started for area %s", area_id)

    def send_colors(self, commands: list[LightColorCommand]) -> None:
        if self._session is None:
            return
        self._session.send(commands)

    async def stop_stream(self) -> None:
        if self._session is None:
            return
        try:
            await self._session.aclose()
        except Exception:
            LOGGER.exception("Error while closing entertainment session")
        self._session = None
        self._active_area_id = ""
        LOGGER.info("Entertainment stream stopped")

    async def _discover_mdns(self, found: dict[str, HueBridge]) -> None:
        try:
            bridges = await _await_maybe(
                discover_bridges(timeout=self._settings.hue_mdns_timeout_seconds)
            )
        except TypeError:
            try:
                bridges = await _await_maybe(discover_bridges())
            except Exception:
                LOGGER.exception("mDNS Hue discovery failed")
                return
        except Exception:
            LOGGER.exception("mDNS Hue discovery failed")
            return
        for bridge in bridges or []:
            host = _attr(bridge, "host", "ip", "address", "internalipaddress")
            if not host:
                continue
            found[host] = HueBridge(
                host=str(host),
                bridge_id=str(_attr(bridge, "id", "bridge_id", "bridgeid") or ""),
                name=str(_attr(bridge, "name") or "Hue Bridge"),
                source="mdns",
            )

    async def _discover_cloud(self, found: dict[str, HueBridge]) -> None:
        timeout = aiohttp.ClientTimeout(total=self._settings.hue_discovery_timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self._settings.hue_discovery_url) as response:
                    if response.status != 200:
                        LOGGER.warning(
                            "Hue cloud discovery returned HTTP %s", response.status
                        )
                        return
                    payload = await response.json()
        except Exception:
            LOGGER.exception("Hue cloud discovery failed")
            return
        if not isinstance(payload, list):
            LOGGER.warning("Hue cloud discovery payload was not a list: %s", type(payload))
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            host = str(item.get("internalipaddress") or "")
            if not host or host in found:
                continue
            found[host] = HueBridge(
                host=host,
                bridge_id=str(item.get("id") or ""),
                name="Hue Bridge",
                source="cloud",
            )


async def _await_maybe(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def color_command(channel_id: int, red: float, green: float, blue: float) -> LightColorCommand:
    return LightColorCommand(
        channel_id=channel_id,
        red=_to_16bit(red),
        green=_to_16bit(green),
        blue=_to_16bit(blue),
    )


def _serialize_area(area: EntertainmentArea) -> HueArea:
    return HueArea(
        id=area.id,
        name=area.name,
        channels=[
            HueChannel(
                channel_id=channel.channel_id,
                name=channel.name,
                position=list(channel.position),
            )
            for channel in area.channels
        ],
    )


def _to_16bit(value: float) -> int:
    return int(max(0.0, min(1.0, value)) * 65535)


def _attr(obj: Any, *names: str) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name]:
                return obj[name]
        return None
    for name in names:
        value = getattr(obj, name, None)
        if value:
            return value
    return None
