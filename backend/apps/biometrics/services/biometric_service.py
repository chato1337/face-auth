"""
Fachada pública del pipeline biométrico.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from apps.accounts.models import BiometricProfile, TenantUser
from apps.biometrics.exceptions import DuplicateBiometricError, NoMatchFoundError
from apps.biometrics.services.embeddings import FaceEmbedder
from apps.biometrics.services.liveness_active import ActiveLivenessChecker
from apps.biometrics.services.liveness_passive import PassiveLivenessClassifier
from apps.biometrics.services.preprocessing import FramePreprocessor
from apps.biometrics.services.vector_matcher import VectorMatcher
from apps.tenants.models import Application


@dataclass
class LivenessReport:
    passed: bool
    active_score: float
    passive_score: float
    reason: str | None = None


@dataclass
class EnrollResult:
    embedding: np.ndarray
    liveness: LivenessReport
    quality_score: float


@dataclass
class AuthResult:
    matched_user: TenantUser | None
    distance: float | None
    liveness: LivenessReport


class BiometricService:
    """Orquesta el pipeline completo. Stateless entre llamadas."""

    def __init__(
        self,
        application: Application,
        *,
        preprocessor: FramePreprocessor | None = None,
        active_liveness: ActiveLivenessChecker | None = None,
        passive_liveness: PassiveLivenessClassifier | None = None,
        embedder: FaceEmbedder | None = None,
        matcher: VectorMatcher | None = None,
    ):
        self.application = application
        self._preprocessor = preprocessor or FramePreprocessor()
        self._active_liveness = active_liveness or ActiveLivenessChecker()
        self._passive_liveness = passive_liveness or PassiveLivenessClassifier()
        self._embedder = embedder or FaceEmbedder()
        self._matcher = matcher or VectorMatcher(application=application)

    def process_enrollment(self, video_bytes: bytes) -> EnrollResult:
        """Flujo B (Registro): valida liveness y extrae embedding; no persiste."""
        batch = self._preprocessor.process(video_bytes)
        active = self._active_liveness.check(batch.frames)
        crops = self._embedder.crop_faces(batch.frames)
        passive = self._passive_liveness.classify(crops, threshold=self.application.liveness_threshold)
        best = self._embedder.pick_best_frame(batch.frames)
        embedding, quality = self._embedder.embed(best)

        duplicate = self._matcher.find_duplicate(embedding)
        if duplicate is not None:
            raise DuplicateBiometricError(
                "Este rostro ya está registrado en esta aplicación.",
                field="video",
            )

        return EnrollResult(
            embedding=embedding,
            liveness=LivenessReport(
                passed=True,
                active_score=active.metrics.score,
                passive_score=passive.score,
            ),
            quality_score=quality,
        )

    def process_authentication(self, video_bytes: bytes) -> AuthResult:
        """Flujo A (Login): liveness + match contra BD del tenant."""
        batch = self._preprocessor.process(video_bytes)
        active = self._active_liveness.check(batch.frames)
        crops = self._embedder.crop_faces(batch.frames)
        passive = self._passive_liveness.classify(crops, threshold=self.application.liveness_threshold)
        best = self._embedder.pick_best_frame(batch.frames)
        embedding, _quality = self._embedder.embed(best)

        match = self._matcher.find_best_match(embedding)
        liveness = LivenessReport(
            passed=True,
            active_score=active.metrics.score,
            passive_score=passive.score,
        )
        if match is None:
            raise NoMatchFoundError("No se encontró coincidencia biométrica.", field="video")

        return AuthResult(
            matched_user=match.user,
            distance=match.distance,
            liveness=liveness,
        )

    def persist_enrollment(
        self,
        user: TenantUser,
        result: EnrollResult,
        *,
        deactivate_previous: bool = True,
    ) -> BiometricProfile:
        """Persiste el embedding tras un EnrollResult exitoso."""
        if deactivate_previous:
            BiometricProfile.objects.filter(user=user, is_active=True).update(is_active=False)

        return BiometricProfile.objects.create(
            user=user,
            application=self.application,
            embedding=result.embedding.astype(np.float32).tolist(),
            liveness_score=result.liveness.passive_score,
            quality_score=result.quality_score,
            is_active=True,
        )
