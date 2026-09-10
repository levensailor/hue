"""Color helpers for lightshow modes."""

from __future__ import annotations

import colorsys


def hsv(hue: float, saturation: float, value: float) -> tuple[float, float, float]:
    red, green, blue = colorsys.hsv_to_rgb(
        hue % 1.0,
        max(0.0, min(1.0, saturation)),
        max(0.0, min(1.0, value)),
    )
    return red, green, blue


def scale(color: tuple[float, float, float], amount: float) -> tuple[float, float, float]:
    amount = max(0.0, min(1.0, amount))
    return color[0] * amount, color[1] * amount, color[2] * amount


def mix(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    amount: float,
) -> tuple[float, float, float]:
    amount = max(0.0, min(1.0, amount))
    return (
        first[0] + (second[0] - first[0]) * amount,
        first[1] + (second[1] - first[1]) * amount,
        first[2] + (second[2] - first[2]) * amount,
    )


def add_flash(
    color: tuple[float, float, float],
    beat: bool,
    amount: float = 0.35,
) -> tuple[float, float, float]:
    if not beat:
        return color
    return mix(color, (1.0, 1.0, 1.0), amount)
