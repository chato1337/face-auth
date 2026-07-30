"""
Pool de instancias de modelos ML reutilizadas a nivel de proceso.

Evita recargar pesos ONNX / MediaPipe / InsightFace en cada request HTTP.
Las instancias son thread-safe para inferencia típica (sesión ORT + FaceAnalysis
en CPU); el acceso al singleton se protege con un lock de inicialización.
"""
from __future__ import annotations

import threading

from apps.biometrics.services.embeddings import FaceEmbedder
from apps.biometrics.services.liveness_active import ActiveLivenessChecker
from apps.biometrics.services.liveness_passive import PassiveLivenessClassifier
from apps.biometrics.services.preprocessing import FramePreprocessor


class ModelPool:
    _lock = threading.Lock()
    _preprocessor: FramePreprocessor | None = None
    _active: ActiveLivenessChecker | None = None
    _passive: PassiveLivenessClassifier | None = None
    _embedder: FaceEmbedder | None = None

    @classmethod
    def get_preprocessor(cls) -> FramePreprocessor:
        with cls._lock:
            if cls._preprocessor is None:
                cls._preprocessor = FramePreprocessor()
            return cls._preprocessor

    @classmethod
    def get_active_liveness(cls) -> ActiveLivenessChecker:
        with cls._lock:
            if cls._active is None:
                cls._active = ActiveLivenessChecker()
            return cls._active

    @classmethod
    def get_passive_liveness(cls) -> PassiveLivenessClassifier:
        with cls._lock:
            if cls._passive is None:
                cls._passive = PassiveLivenessClassifier()
            return cls._passive

    @classmethod
    def get_embedder(cls) -> FaceEmbedder:
        with cls._lock:
            if cls._embedder is None:
                cls._embedder = FaceEmbedder()
            return cls._embedder

    @classmethod
    def reset_for_tests(cls) -> None:
        """Solo para tests: descarta singletons."""
        with cls._lock:
            cls._preprocessor = None
            cls._active = None
            cls._passive = None
            cls._embedder = None
