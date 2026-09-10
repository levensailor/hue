"""FFT bands, RMS energy, spectral centroid, and onset/beat detection."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

BAND_EDGES_HZ = (20.0, 80.0, 160.0, 400.0, 1000.0, 2500.0, 6000.0, 16000.0)
METER_BAND_COUNT = 16


@dataclass
class AnalysisFrame:
    rms: float
    bass: float
    mid: float
    high: float
    centroid: float
    beat: bool
    bands: list[float]
    channel_energy: list[float]


@dataclass
class AudioAnalyzer:
    """Stateful analyzer so beat detection can track flux over time."""

    sample_rate: int
    sensitivity: float = 1.0
    _previous_bass: float = 0.0
    _beat_hold: int = 0
    _smoothed_bands: np.ndarray = field(default_factory=lambda: np.zeros(7))
    _smoothed_meters: np.ndarray = field(default_factory=lambda: np.zeros(METER_BAND_COUNT))

    def analyze(self, block: np.ndarray) -> AnalysisFrame:
        if block.ndim == 1:
            block = block[:, np.newaxis]

        channel_energy = [
            float(np.sqrt(np.mean(np.square(block[:, channel]))))
            for channel in range(block.shape[1])
        ]
        mono = np.mean(block, axis=1)
        window = np.hanning(len(mono))
        spectrum = np.abs(np.fft.rfft(mono * window))
        freqs = np.fft.rfftfreq(len(mono), d=1.0 / self.sample_rate)
        if spectrum.size:
            spectrum = spectrum / (np.max(spectrum) + 1e-9)

        band_powers = self._band_powers(spectrum, freqs, BAND_EDGES_HZ)
        meters = self._band_powers(
            spectrum,
            freqs,
            np.geomspace(40.0, min(16000.0, self.sample_rate / 2.0), METER_BAND_COUNT + 1),
        )

        self._smoothed_bands = self._smooth(self._smoothed_bands, band_powers)
        self._smoothed_meters = self._smooth(self._smoothed_meters, meters)

        bass = float(np.clip(np.mean(self._smoothed_bands[0:2]) * self.sensitivity, 0.0, 1.0))
        mid = float(np.clip(np.mean(self._smoothed_bands[2:5]) * self.sensitivity, 0.0, 1.0))
        high = float(np.clip(np.mean(self._smoothed_bands[5:]) * self.sensitivity, 0.0, 1.0))
        rms = float(np.clip(np.sqrt(np.mean(np.square(mono))) * 4.0 * self.sensitivity, 0.0, 1.0))
        centroid = self._centroid(spectrum, freqs)
        beat = self._detect_beat(bass)

        return AnalysisFrame(
            rms=rms,
            bass=bass,
            mid=mid,
            high=high,
            centroid=centroid,
            beat=beat,
            bands=[float(value) for value in self._smoothed_meters],
            channel_energy=channel_energy,
        )

    def _band_powers(self, spectrum: np.ndarray, freqs: np.ndarray, edges) -> np.ndarray:
        powers: list[float] = []
        edges = list(edges)
        for low, high in zip(edges[:-1], edges[1:]):
            mask = (freqs >= low) & (freqs < high)
            powers.append(float(np.sqrt(np.mean(np.square(spectrum[mask])))) if np.any(mask) else 0.0)
        return np.array(powers, dtype=float)

    def _smooth(self, previous: np.ndarray, current: np.ndarray) -> np.ndarray:
        if previous.shape != current.shape:
            previous = np.zeros_like(current)
        attack = np.where(current > previous, 0.55, 0.18)
        return previous + attack * (current - previous)

    def _centroid(self, spectrum: np.ndarray, freqs: np.ndarray) -> float:
        weight = float(np.sum(spectrum))
        if weight <= 1e-9:
            return 0.2
        hz = float(np.sum(spectrum * freqs) / weight)
        return float(np.clip((hz - 80.0) / 4000.0, 0.0, 1.0))

    def _detect_beat(self, bass: float) -> bool:
        flux = bass - self._previous_bass
        self._previous_bass = bass
        if self._beat_hold > 0:
            self._beat_hold -= 1
            return False
        if flux > 0.12 and bass > 0.28:
            self._beat_hold = 4
            return True
        return False
