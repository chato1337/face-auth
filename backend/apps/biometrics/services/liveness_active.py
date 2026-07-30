"""
Liveness activo: parpadeo (EAR) + variación de pose con MediaPipe Face Landmarker (Tasks API).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings

from apps.biometrics.exceptions import FaceNotFoundError, ModelNotAvailableError, SpoofDetectedError

# Índices Face Landmarker (~478) compatibles con el antiguo Face Mesh para ojos/pose.
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
NOSE_TIP = 1
CHIN = 152
LEFT_FACE = 234
RIGHT_FACE = 454

FACE_LANDMARKER_FILENAME = "face_landmarker.task"


@dataclass(frozen=True)
class ActiveLivenessMetrics:
    blink_count: int
    min_ear: float
    mean_ear: float
    yaw_delta: float
    pitch_delta: float
    frames_with_face: int
    score: float


@dataclass(frozen=True)
class ActiveLivenessResult:
    passed: bool
    metrics: ActiveLivenessMetrics
    reason: str | None = None


class ActiveLivenessChecker:
    """
    Detecta presencia de vida mediante:
    - EAR (Eye Aspect Ratio) → parpadeos
    - Variación de yaw/pitch entre frames → cabeza no estática (anti-foto)
    """

    EAR_BLINK_THRESHOLD = 0.21
    MIN_BLINKS = 1
    MIN_POSE_DELTA = 3.0  # grados acumulados (yaw+pitch)
    MIN_FACE_RATIO = 0.5

    def __init__(self, model_path: Path | None = None):
        self.model_path = model_path or (Path(settings.ML_MODELS_DIR) / FACE_LANDMARKER_FILENAME)
        self._landmarker = None

    def _ensure_landmarker(self):
        if self._landmarker is not None:
            return
        if not self.model_path.exists():
            raise ModelNotAvailableError(
                f"Modelo Face Landmarker no encontrado: {self.model_path}. "
                "Ejecuta: pipenv run python manage.py download_ml_models",
                field=None,
            )
        try:
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
        except ImportError as exc:
            raise ModelNotAvailableError("mediapipe.tasks no disponible.", field=None) from exc

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)

    def check(self, frames: list[np.ndarray]) -> ActiveLivenessResult:
        if not frames:
            raise FaceNotFoundError("No hay frames para analizar liveness activo.", field="video")

        self._ensure_landmarker()
        assert self._landmarker is not None

        from mediapipe import Image as MpImage
        from mediapipe import ImageFormat

        ears: list[float] = []
        yaws: list[float] = []
        pitches: list[float] = []
        faces = 0

        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = MpImage(image_format=ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            result = self._landmarker.detect(mp_image)
            if not result.face_landmarks:
                continue
            faces += 1
            lm = result.face_landmarks[0]
            h, w = frame.shape[:2]
            pts = np.array([(p.x * w, p.y * h, p.z * w) for p in lm], dtype=np.float32)

            left_ear = self._eye_aspect_ratio(pts, LEFT_EYE)
            right_ear = self._eye_aspect_ratio(pts, RIGHT_EYE)
            ears.append((left_ear + right_ear) / 2.0)

            yaw, pitch = self._estimate_pose(pts)
            yaws.append(yaw)
            pitches.append(pitch)

        face_ratio = faces / len(frames)
        if face_ratio < self.MIN_FACE_RATIO or not ears:
            raise FaceNotFoundError(
                "No se detectó un rostro de forma consistente en el clip.",
                field="video",
            )

        blink_count = self._count_blinks(ears)
        yaw_delta = float(np.ptp(yaws)) if yaws else 0.0
        pitch_delta = float(np.ptp(pitches)) if pitches else 0.0
        pose_delta = yaw_delta + pitch_delta
        min_ear = float(np.min(ears))
        mean_ear = float(np.mean(ears))

        blink_score = min(1.0, blink_count / max(self.MIN_BLINKS, 1))
        pose_score = min(1.0, pose_delta / max(self.MIN_POSE_DELTA, 1e-6))
        score = 0.55 * blink_score + 0.45 * pose_score

        reasons: list[str] = []
        if blink_count < self.MIN_BLINKS:
            reasons.append("no se detectó parpadeo")
        if pose_delta < self.MIN_POSE_DELTA:
            reasons.append("cabeza demasiado estática (posible foto/pantalla)")

        passed = len(reasons) == 0
        metrics = ActiveLivenessMetrics(
            blink_count=blink_count,
            min_ear=min_ear,
            mean_ear=mean_ear,
            yaw_delta=yaw_delta,
            pitch_delta=pitch_delta,
            frames_with_face=faces,
            score=score,
        )
        if not passed:
            raise SpoofDetectedError(
                "Liveness activo fallido: " + "; ".join(reasons),
                field="video",
            )

        return ActiveLivenessResult(passed=True, metrics=metrics)

    @staticmethod
    def _eye_aspect_ratio(pts: np.ndarray, indices: list[int]) -> float:
        p = pts[indices][:, :2]
        a = np.linalg.norm(p[1] - p[5])
        b = np.linalg.norm(p[2] - p[4])
        c = np.linalg.norm(p[0] - p[3])
        if c < 1e-6:
            return 0.0
        return float((a + b) / (2.0 * c))

    @staticmethod
    def _estimate_pose(pts: np.ndarray) -> tuple[float, float]:
        nose = pts[NOSE_TIP][:2]
        chin = pts[CHIN][:2]
        left = pts[LEFT_FACE][:2]
        right = pts[RIGHT_FACE][:2]

        mid_x = (left[0] + right[0]) / 2.0
        face_width = max(np.linalg.norm(right - left), 1e-6)
        yaw = float(np.degrees(np.arcsin(np.clip((nose[0] - mid_x) / (face_width / 2.0), -1.0, 1.0))))

        face_height = max(abs(chin[1] - nose[1]), 1e-6)
        pitch = float(np.degrees(np.arctan2(nose[1] - (nose[1] + chin[1]) / 2.0, face_height)))
        return yaw, pitch

    @staticmethod
    def _count_blinks(ears: list[float], threshold: float | None = None) -> int:
        thr = ActiveLivenessChecker.EAR_BLINK_THRESHOLD if threshold is None else threshold
        blinks = 0
        closed = False
        for ear in ears:
            if ear < thr and not closed:
                closed = True
            elif ear >= thr and closed:
                blinks += 1
                closed = False
        return blinks

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
