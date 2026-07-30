"""
Pruebas de condiciones adversas del preprocessor (sin pesos ML).
Simula poca luz, resolución insuficiente y video demasiado corto.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from apps.biometrics.exceptions import InvalidVideoError, LowQualityCaptureError
from apps.biometrics.services.preprocessing import FramePreprocessor


def _write_video(frames: list[np.ndarray], fps: float = 15.0) -> bytes:
    h, w = frames[0].shape[:2]
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = Path(tmp.name)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        writer.write(f)
    writer.release()
    data = path.read_bytes()
    path.unlink(missing_ok=True)
    return data


class TestAdverseCaptureConditions:
    def test_low_light_rejected(self):
        # Brillo ~10 << MIN_BRIGHTNESS 40
        frames = [np.full((480, 640, 3), 10, dtype=np.uint8) for _ in range(45)]
        with pytest.raises(LowQualityCaptureError) as exc:
            FramePreprocessor().process(_write_video(frames))
        assert exc.value.code == "low_quality_capture"

    def test_resolution_too_low(self):
        frames = [np.full((120, 160, 3), 140, dtype=np.uint8) for _ in range(45)]
        with pytest.raises(LowQualityCaptureError) as exc:
            FramePreprocessor().process(_write_video(frames))
        assert exc.value.code == "low_quality_capture"

    def test_too_short_duration(self):
        frames = [np.full((480, 640, 3), 140, dtype=np.uint8) for _ in range(5)]
        with pytest.raises((LowQualityCaptureError, InvalidVideoError)):
            FramePreprocessor().process(_write_video(frames, fps=30.0))

    def test_oversized_bytes_rejected(self):
        huge = b"\x00" * (FramePreprocessor.MAX_BYTES + 1)
        with pytest.raises(InvalidVideoError) as exc:
            FramePreprocessor().process(huge)
        assert exc.value.code == "invalid_video"
