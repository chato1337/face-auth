"""
Extracción y validación de frames de video (OpenCV).
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from apps.biometrics.exceptions import InvalidVideoError, LowQualityCaptureError


@dataclass(frozen=True)
class FrameBatch:
    frames: list[np.ndarray]
    fps: float
    width: int
    height: int
    duration_sec: float
    mean_brightness: float


class FramePreprocessor:
    """
    Decodifica video bytes → frames muestreados + metadata de calidad.
    Acepta mp4/webm (y lo que OpenCV pueda abrir vía archivo temporal).
    """

    MIN_FPS = 8.0
    MIN_WIDTH = 320
    MIN_HEIGHT = 240
    MIN_DURATION_SEC = 1.0
    MAX_DURATION_SEC = 6.0
    MIN_BRIGHTNESS = 40.0
    MAX_BRIGHTNESS = 220.0
    TARGET_FRAME_COUNT = 16
    MAX_BYTES = 15 * 1024 * 1024  # 15 MB

    def process(self, video_bytes: bytes) -> FrameBatch:
        if not video_bytes:
            raise InvalidVideoError("Video vacío.", field="video")
        if len(video_bytes) > self.MAX_BYTES:
            raise InvalidVideoError(
                f"Video supera el tamaño máximo ({self.MAX_BYTES // (1024 * 1024)} MB).",
                field="video",
            )

        suffix = self._guess_suffix(video_bytes)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(video_bytes)
            tmp.flush()
            return self._extract_from_path(Path(tmp.name))

    def _guess_suffix(self, video_bytes: bytes) -> str:
        if video_bytes[:4] == b"\x1aE\xdf\xa3":
            return ".webm"
        if len(video_bytes) > 8 and video_bytes[4:8] == b"ftyp":
            return ".mp4"
        return ".mp4"

    def _extract_from_path(self, path: Path) -> FrameBatch:
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            raise InvalidVideoError("No se pudo abrir el video (formato corrupto o no soportado).", field="video")

        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                raise LowQualityCaptureError(
                    f"Resolución insuficiente ({width}x{height}). Mínimo {self.MIN_WIDTH}x{self.MIN_HEIGHT}.",
                    field="video",
                )

            raw_frames: list[np.ndarray] = []
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                raw_frames.append(frame)

            if not raw_frames:
                raise InvalidVideoError("El video no contiene frames legibles.", field="video")

            # Algunos contenedores reportan fps=0; estimar desde conteo si hay duración implícita.
            if fps <= 0 and frame_count > 0:
                fps = float(frame_count) / max(self.MIN_DURATION_SEC, 1.0)
            if fps <= 0:
                fps = 15.0

            duration_sec = len(raw_frames) / fps
            if duration_sec < self.MIN_DURATION_SEC:
                raise LowQualityCaptureError(
                    f"Clip demasiado corto ({duration_sec:.2f}s). Mínimo {self.MIN_DURATION_SEC}s.",
                    field="video",
                )
            if duration_sec > self.MAX_DURATION_SEC:
                raise LowQualityCaptureError(
                    f"Clip demasiado largo ({duration_sec:.2f}s). Máximo {self.MAX_DURATION_SEC}s.",
                    field="video",
                )
            if fps < self.MIN_FPS:
                raise LowQualityCaptureError(
                    f"FPS insuficiente ({fps:.1f}). Mínimo {self.MIN_FPS}.",
                    field="video",
                )

            sampled = self._sample_frames(raw_frames, self.TARGET_FRAME_COUNT)
            brightness = float(np.mean([float(np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))) for f in sampled]))
            if brightness < self.MIN_BRIGHTNESS:
                raise LowQualityCaptureError(
                    "Iluminación insuficiente. Mejora la luz del entorno.",
                    field="video",
                )
            if brightness > self.MAX_BRIGHTNESS:
                raise LowQualityCaptureError(
                    "Imagen sobreexpuesta. Reduce la luz directa.",
                    field="video",
                )

            return FrameBatch(
                frames=sampled,
                fps=fps,
                width=width,
                height=height,
                duration_sec=duration_sec,
                mean_brightness=brightness,
            )
        finally:
            capture.release()

    @staticmethod
    def _sample_frames(frames: list[np.ndarray], target: int) -> list[np.ndarray]:
        if len(frames) <= target:
            return frames
        indices = np.linspace(0, len(frames) - 1, target, dtype=int)
        return [frames[i] for i in indices]
