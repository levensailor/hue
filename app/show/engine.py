"""Turn analysis frames into per-channel Hue colors."""

from __future__ import annotations

from app.audio.analyzer import AnalysisFrame
from app.hue.bridge import color_command
from app.models import HueChannel, ShowMode
from app.show.palettes import add_flash, hsv, mix, scale
from hue_entertainment import LightColorCommand


class ShowEngine:
    """Mode-aware mapper from audio features to Entertainment RGB commands."""

    def colors(
        self,
        frame: AnalysisFrame,
        channels: list[HueChannel],
        mode: ShowMode,
        brightness: float,
        saturation: float,
    ) -> list[LightColorCommand]:
        ordered = sorted(channels, key=lambda channel: channel.position[0] if channel.position else 0.0)
        if not ordered:
            return []
        commands: list[LightColorCommand] = []
        for index, channel in enumerate(ordered):
            position = index / max(1, len(ordered) - 1)
            red, green, blue = self._color_for(frame, mode, position, saturation)
            red, green, blue = scale((red, green, blue), brightness)
            commands.append(color_command(channel.channel_id, red, green, blue))
        return commands

    def preview(
        self,
        frame: AnalysisFrame,
        channels: list[HueChannel],
        mode: ShowMode,
        brightness: float,
        saturation: float,
    ) -> list[dict[str, float | int]]:
        commands = self.colors(frame, channels, mode, brightness, saturation)
        return [
            {
                "channel_id": command.channel_id,
                "r": command.red / 65535.0,
                "g": command.green / 65535.0,
                "b": command.blue / 65535.0,
            }
            for command in commands
        ]

    def _color_for(
        self,
        frame: AnalysisFrame,
        mode: ShowMode,
        position: float,
        saturation: float,
    ) -> tuple[float, float, float]:
        if mode == "pulse":
            color = hsv(0.72 - frame.centroid * 0.55, saturation, 0.25 + frame.rms * 0.75)
            return add_flash(color, frame.beat, 0.45)
        if mode == "studio":
            warmth = mix((0.85, 0.42, 0.12), (1.0, 0.78, 0.35), frame.mid)
            kick = mix(warmth, (1.0, 0.92, 0.7), frame.bass * 0.7)
            return add_flash(scale(kick, 0.35 + frame.rms * 0.65), frame.beat, 0.25)
        if mode == "fire":
            heat = mix((0.35, 0.02, 0.0), (1.0, 0.55, 0.05), frame.bass)
            heat = mix(heat, (1.0, 0.9, 0.35), frame.high * 0.6)
            return add_flash(scale(heat, 0.3 + frame.rms * 0.7), frame.beat, 0.3)
        if mode == "ocean":
            water = mix((0.0, 0.08, 0.35), (0.0, 0.55, 0.85), frame.mid)
            water = mix(water, (0.75, 0.95, 1.0), frame.high * 0.5)
            return add_flash(scale(water, 0.3 + frame.rms * 0.7), frame.beat, 0.28)
        if mode == "split":
            energy = _channel_energy(frame, position)
            color = hsv(0.08 + position * 0.55, saturation, 0.2 + energy * 0.8)
            return add_flash(color, frame.beat and energy > 0.35, 0.35)
        if mode == "logic":
            # Recording-friendly: less strobe, more sustained musical color.
            base = hsv(0.08 + frame.centroid * 0.18, saturation * 0.75, 0.22 + frame.mid * 0.45)
            accent = hsv(0.62 - position * 0.12, saturation, frame.high * 0.55)
            blended = mix(base, accent, 0.35)
            if frame.beat:
                blended = mix(blended, (1.0, 0.72, 0.38), 0.22)
            return blended
        # spectrum (default): left=bass, center=mid, right=high
        band = frame.bass if position < 0.33 else frame.mid if position < 0.66 else frame.high
        hue = 0.75 - position * 0.62 + frame.centroid * 0.08
        color = hsv(hue, saturation, 0.18 + band * 0.82)
        return add_flash(color, frame.beat, 0.32)


def _channel_energy(frame: AnalysisFrame, position: float) -> float:
    energies = frame.channel_energy or [frame.rms]
    if len(energies) == 1:
        return min(1.0, energies[0] * 4.0)
    index = int(round(position * (len(energies) - 1)))
    return min(1.0, energies[index] * 4.0)
