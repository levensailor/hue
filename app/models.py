"""Pydantic request and response models for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ShowMode = Literal["spectrum", "pulse", "studio", "fire", "ocean", "split", "logic"]


class AudioDevice(BaseModel):
    index: int
    name: str
    host_api: str
    max_input_channels: int
    default_samplerate: float
    is_ssl: bool
    is_default: bool


class AudioDevicesResponse(BaseModel):
    devices: list[AudioDevice]
    default_index: int | None = None


class HueBridge(BaseModel):
    host: str
    bridge_id: str = ""
    name: str = ""
    source: str


class HueBridgesResponse(BaseModel):
    bridges: list[HueBridge]


class PairRequest(BaseModel):
    host: str = Field(min_length=1)
    device_type: str | None = None


class PairResponse(BaseModel):
    host: str
    paired: bool
    message: str


class HueChannel(BaseModel):
    channel_id: int
    name: str
    position: list[float]


class HueArea(BaseModel):
    id: str
    name: str
    channels: list[HueChannel]


class HueAreasResponse(BaseModel):
    areas: list[HueArea]
    paired: bool
    host: str = ""


class AppSettingsPayload(BaseModel):
    audio_device_index: int | None = None
    channel_map: list[int] = Field(default_factory=lambda: [0, 1])
    area_id: str = ""
    mode: ShowMode = "spectrum"
    sensitivity: float = Field(default=1.0, ge=0.1, le=4.0)
    brightness: float = Field(default=0.85, ge=0.05, le=1.0)
    saturation: float = Field(default=0.95, ge=0.0, le=1.0)
    hue_host: str = ""

    @field_validator("channel_map")
    @classmethod
    def require_settings_channels(cls, value: list[int]) -> list[int]:
        cleaned = [index for index in value if index >= 0]
        return cleaned or [0, 1]


class ShowStartRequest(BaseModel):
    audio_device_index: int
    channel_map: list[int] = Field(default_factory=lambda: [0, 1])
    area_id: str = Field(min_length=1)
    mode: ShowMode = "spectrum"
    sensitivity: float = Field(default=1.0, ge=0.1, le=4.0)
    brightness: float = Field(default=0.85, ge=0.05, le=1.0)
    saturation: float = Field(default=0.95, ge=0.0, le=1.0)

    @field_validator("channel_map")
    @classmethod
    def require_channels(cls, value: list[int]) -> list[int]:
        cleaned = [index for index in value if index >= 0]
        return cleaned or [0, 1]


class ShowStatus(BaseModel):
    running: bool
    mode: str = ""
    area_id: str = ""
    audio_device_index: int | None = None
    message: str = ""


class HealthResponse(BaseModel):
    status: str
    app_name: str
    author: str
