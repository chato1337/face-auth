"""
Fachada pública del pipeline biométrico.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import numpy as np

from apps.accounts.models import BiometricProfile, TenantUser
from apps.biometrics.exceptions import BiometricPipelineError, DuplicateBiometricError, NoMatchFoundError
from apps.biometrics.services.embeddings import FaceEmbedder
from apps.biometrics.services.liveness_active import ActiveLivenessChecker
from apps.biometrics.services.liveness_passive import PassiveLivenessClassifier
from apps.biometrics.services.model_pool import ModelPool
from apps.biometrics.services.preprocessing import FramePreprocessor
from apps.biometrics.services.vector_matcher import VectorMatcher
from apps.tenants.models import Application

logger = logging.getLogger("apps.biometrics.pipeline")

T = TypeVar("T")


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


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
        # Por defecto reutiliza singletons de proceso (Fase 5 — pooling).
        self._preprocessor = preprocessor or ModelPool.get_preprocessor()
        self._active_liveness = active_liveness or ModelPool.get_active_liveness()
        self._passive_liveness = passive_liveness or ModelPool.get_passive_liveness()
        self._embedder = embedder or ModelPool.get_embedder()
        self._matcher = matcher or VectorMatcher(application=application)

    def _run_stage(self, flow: str, stage: str, fn: Callable[[], T]) -> T:
        """Ejecuta una etapa del pipeline con timing y log de éxito/fallo."""
        app_id = self.application.app_id
        t0 = time.perf_counter()
        logger.info("[%s] stage=%s START app_id=%s", flow, stage, app_id)
        try:
            result = fn()
        except BiometricPipelineError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "[%s] stage=%s FAIL app_id=%s code=%s http=%s duration_ms=%.1f message=%s field=%s",
                flow,
                stage,
                app_id,
                exc.code,
                exc.http_status,
                elapsed_ms,
                exc.message,
                exc.field,
            )
            raise
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.exception(
                "[%s] stage=%s ERROR app_id=%s duration_ms=%.1f (unexpected)",
                flow,
                stage,
                app_id,
                elapsed_ms,
            )
            raise
        else:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "[%s] stage=%s OK app_id=%s duration_ms=%.1f",
                flow,
                stage,
                app_id,
                elapsed_ms,
            )
            return result

    def process_enrollment(self, video_bytes: bytes) -> EnrollResult:
        """Flujo B (Registro): valida liveness y extrae embedding; no persiste."""
        flow = "enroll"
        t0 = time.perf_counter()
        logger.info(
            "[%s] PIPELINE START app_id=%s video_bytes=%d liveness_threshold=%.3f match_threshold=%.3f",
            flow,
            self.application.app_id,
            len(video_bytes),
            self.application.liveness_threshold,
            self.application.match_threshold,
        )

        batch = self._run_stage(flow, "1_preprocessing", lambda: self._preprocessor.process(video_bytes))
        logger.info(
            "[%s] stage=1_preprocessing metrics frames=%d fps=%.2f size=%dx%d "
            "duration_sec=%.2f brightness=%.1f",
            flow,
            len(batch.frames),
            batch.fps,
            batch.width,
            batch.height,
            batch.duration_sec,
            batch.mean_brightness,
        )

        active = self._run_stage(flow, "2_liveness_active", lambda: self._active_liveness.check(batch.frames))
        self._log_active_metrics(flow, active.metrics)

        crops = self._run_stage(flow, "3_face_crops", lambda: self._embedder.crop_faces(batch.frames))
        logger.info("[%s] stage=3_face_crops metrics crops=%d", flow, len(crops))

        threshold = self.application.liveness_threshold
        passive = self._run_stage(
            flow,
            "4_liveness_passive",
            lambda: self._passive_liveness.classify(crops, threshold=threshold),
        )
        self._log_passive_metrics(flow, passive, threshold)

        best = self._run_stage(flow, "5_pick_best_frame", lambda: self._embedder.pick_best_frame(batch.frames))
        embedding, quality = self._run_stage(flow, "6_embedding", lambda: self._embedder.embed(best))
        logger.info(
            "[%s] stage=6_embedding metrics dim=%d norm=%.4f quality=%.3f",
            flow,
            embedding.shape[0],
            float(np.linalg.norm(embedding)),
            quality,
        )

        t_dup = time.perf_counter()
        logger.info("[%s] stage=7_duplicate_check START app_id=%s", flow, self.application.app_id)
        duplicate = self._matcher.find_duplicate(embedding)
        dup_ms = (time.perf_counter() - t_dup) * 1000
        if duplicate is not None:
            logger.warning(
                "[%s] stage=7_duplicate_check FAIL app_id=%s code=duplicate_biometric "
                "duration_ms=%.1f distance=%.4f user_id=%s",
                flow,
                self.application.app_id,
                dup_ms,
                duplicate.distance,
                duplicate.user.id,
            )
            raise DuplicateBiometricError(
                "Este rostro ya está registrado en esta aplicación.",
                field="video",
            )
        logger.info(
            "[%s] stage=7_duplicate_check OK app_id=%s duration_ms=%.1f no_duplicate",
            flow,
            self.application.app_id,
            dup_ms,
        )

        total_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "[%s] PIPELINE OK app_id=%s total_ms=%.1f quality=%.3f active=%.3f passive=%.3f",
            flow,
            self.application.app_id,
            total_ms,
            quality,
            float(getattr(active.metrics, "score", 0.0)),
            float(getattr(passive, "score", 0.0)),
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
        flow = "auth"
        t0 = time.perf_counter()
        logger.info(
            "[%s] PIPELINE START app_id=%s video_bytes=%d liveness_threshold=%.3f match_threshold=%.3f",
            flow,
            self.application.app_id,
            len(video_bytes),
            self.application.liveness_threshold,
            self.application.match_threshold,
        )

        batch = self._run_stage(flow, "1_preprocessing", lambda: self._preprocessor.process(video_bytes))
        logger.info(
            "[%s] stage=1_preprocessing metrics frames=%d fps=%.2f size=%dx%d "
            "duration_sec=%.2f brightness=%.1f",
            flow,
            len(batch.frames),
            batch.fps,
            batch.width,
            batch.height,
            batch.duration_sec,
            batch.mean_brightness,
        )

        active = self._run_stage(flow, "2_liveness_active", lambda: self._active_liveness.check(batch.frames))
        self._log_active_metrics(flow, active.metrics)

        crops = self._run_stage(flow, "3_face_crops", lambda: self._embedder.crop_faces(batch.frames))
        logger.info("[%s] stage=3_face_crops metrics crops=%d", flow, len(crops))

        threshold = self.application.liveness_threshold
        passive = self._run_stage(
            flow,
            "4_liveness_passive",
            lambda: self._passive_liveness.classify(crops, threshold=threshold),
        )
        self._log_passive_metrics(flow, passive, threshold)

        best = self._run_stage(flow, "5_pick_best_frame", lambda: self._embedder.pick_best_frame(batch.frames))
        embedding, quality = self._run_stage(flow, "6_embedding", lambda: self._embedder.embed(best))
        logger.info(
            "[%s] stage=6_embedding metrics dim=%d quality=%.3f",
            flow,
            embedding.shape[0],
            quality,
        )

        match = self._run_stage(flow, "7_vector_match", lambda: self._matcher.find_best_match(embedding))
        liveness = LivenessReport(
            passed=True,
            active_score=active.metrics.score,
            passive_score=passive.score,
        )
        if match is None:
            logger.warning(
                "[%s] stage=7_vector_match FAIL app_id=%s code=no_match threshold=%.3f",
                flow,
                self.application.app_id,
                self.application.match_threshold,
            )
            raise NoMatchFoundError("No se encontró coincidencia biométrica.", field="video")

        total_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "[%s] PIPELINE OK app_id=%s total_ms=%.1f user_id=%s distance=%.4f threshold=%.3f",
            flow,
            self.application.app_id,
            total_ms,
            match.user.id,
            match.distance,
            self.application.match_threshold,
        )

        return AuthResult(
            matched_user=match.user,
            distance=match.distance,
            liveness=liveness,
        )

    @staticmethod
    def _log_active_metrics(flow: str, metrics) -> None:
        logger.info(
            "[%s] stage=2_liveness_active metrics score=%.3f blinks=%s min_ear=%s "
            "mean_ear=%s yaw_delta=%s pitch_delta=%s frames_with_face=%s",
            flow,
            float(getattr(metrics, "score", 0.0)),
            getattr(metrics, "blink_count", "?"),
            _fmt(getattr(metrics, "min_ear", None)),
            _fmt(getattr(metrics, "mean_ear", None)),
            _fmt(getattr(metrics, "yaw_delta", None)),
            _fmt(getattr(metrics, "pitch_delta", None)),
            getattr(metrics, "frames_with_face", "?"),
        )

    @staticmethod
    def _log_passive_metrics(flow: str, passive, threshold: float) -> None:
        frame_scores = getattr(passive, "frame_scores", None) or []
        logger.info(
            "[%s] stage=4_liveness_passive metrics score=%.3f threshold=%.3f frame_scores=%s",
            flow,
            float(getattr(passive, "score", 0.0)),
            threshold,
            [round(float(s), 3) for s in frame_scores],
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

        profile = BiometricProfile.objects.create(
            user=user,
            application=self.application,
            embedding=result.embedding.astype(np.float32).tolist(),
            liveness_score=result.liveness.passive_score,
            quality_score=result.quality_score,
            is_active=True,
        )
        logger.info(
            "[enroll] stage=8_persist OK app_id=%s user_id=%s profile_id=%s "
            "liveness=%.3f quality=%.3f",
            self.application.app_id,
            user.id,
            profile.id,
            result.liveness.passive_score,
            result.quality_score,
        )
        return profile
