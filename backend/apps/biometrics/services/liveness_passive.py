"""
Liveness pasivo: MiniFASNetV2 vía ONNXRuntime.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from apps.biometrics.exceptions import ModelNotAvailableError, SpoofDetectedError
from django.conf import settings


@dataclass(frozen=True)
class PassiveLivenessResult:
    score: float
    frame_scores: list[float]
    passed: bool


class PassiveLivenessClassifier:
    """
    Clasificador anti-spoofing pasivo.
    Espera `MiniFASNetV2.onnx` en ML_MODELS_DIR (ver download_ml_models).
    """

    MODEL_FILENAME = "MiniFASNetV2.onnx"
    INPUT_SIZE = (80, 80)

    def __init__(self, model_path: Path | None = None):
        self.model_path = model_path or (Path(settings.ML_MODELS_DIR) / self.MODEL_FILENAME)
        self._session = None

    def _ensure_session(self):
        if self._session is not None:
            return
        if not self.model_path.exists():
            raise ModelNotAvailableError(
                f"Modelo no encontrado: {self.model_path}. "
                "Ejecuta: pipenv run python manage.py download_ml_models",
                field=None,
            )
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ModelNotAvailableError("onnxruntime no está instalado.", field=None) from exc

        self._session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )

    def classify(self, face_crops: list[np.ndarray], threshold: float) -> PassiveLivenessResult:
        if not face_crops:
            raise SpoofDetectedError("Sin recortes de rostro para liveness pasivo.", field="video")

        self._ensure_session()
        assert self._session is not None

        input_name = self._session.get_inputs()[0].name
        scores: list[float] = []
        for crop in face_crops:
            tensor = self._preprocess(crop)
            outputs = self._session.run(None, {input_name: tensor})
            scores.append(self._score_from_output(outputs[0]))

        aggregate = float(np.mean(scores))
        passed = aggregate >= threshold
        if not passed:
            raise SpoofDetectedError(
                f"Liveness pasivo fallido (score={aggregate:.3f} < umbral={threshold:.3f}).",
                field="video",
            )
        return PassiveLivenessResult(score=aggregate, frame_scores=scores, passed=True)

    def _preprocess(self, bgr: np.ndarray) -> np.ndarray:
        resized = cv2.resize(bgr, self.INPUT_SIZE)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        # NCHW
        return np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]

    @staticmethod
    def _score_from_output(output: np.ndarray) -> float:
        """
        MiniFASNet suele devolver logits [fake, real] o probabilidad de real.
        Normalizamos a score 'real' en [0, 1].
        """
        arr = np.asarray(output).reshape(-1).astype(np.float64)
        if arr.size == 1:
            val = float(arr[0])
            if 0.0 <= val <= 1.0:
                return val
            return float(1.0 / (1.0 + np.exp(-val)))
        # Softmax sobre clases; asumimos índice 1 = real si hay 2+ clases
        exp = np.exp(arr - np.max(arr))
        probs = exp / np.sum(exp)
        if probs.size >= 2:
            return float(probs[1])
        return float(probs[0])
