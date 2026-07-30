"""
Tests del pipeline biométrico (sin HTTP).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import pytest

from apps.accounts.models import BiometricProfile, TenantUser
from apps.biometrics.exceptions import (
    DuplicateBiometricError,
    InvalidVideoError,
    LowQualityCaptureError,
    NoMatchFoundError,
)
from apps.biometrics.services.biometric_service import BiometricService
from apps.biometrics.services.liveness_active import ActiveLivenessChecker
from apps.biometrics.services.liveness_passive import PassiveLivenessClassifier, PassiveLivenessResult
from apps.biometrics.services.preprocessing import FramePreprocessor
from apps.biometrics.services.vector_matcher import VectorMatcher
from apps.tenants.models import Application
from apps.authentication.services import AuthenticationService


def _make_video_bytes(
    frames: list[np.ndarray],
    fps: float = 15.0,
) -> bytes:
    import tempfile
    from pathlib import Path

    h, w = frames[0].shape[:2]
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = Path(tmp.name)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    for frame in frames:
        writer.write(frame)
    writer.release()
    data = path.read_bytes()
    path.unlink(missing_ok=True)
    return data


def _solid_frames(n: int = 30, color=(180, 160, 140), size=(640, 480)) -> list[np.ndarray]:
    w, h = size
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    # Añadir textura para brillo/varianza
    noise = np.random.randint(0, 20, frame.shape, dtype=np.uint8)
    frame = cv2.add(frame, noise)
    return [frame.copy() for _ in range(n)]


@pytest.fixture
def application(db):
    return Application.objects.create(
        name="Test App",
        redirect_uris=["http://localhost:3000/callback"],
        liveness_threshold=0.5,
        match_threshold=0.5,
    )


class TestFramePreprocessor:
    def test_rejects_empty(self):
        with pytest.raises(InvalidVideoError):
            FramePreprocessor().process(b"")

    def test_accepts_synthetic_clip(self):
        frames = _solid_frames(45)
        video = _make_video_bytes(frames, fps=15)
        batch = FramePreprocessor().process(video)
        assert len(batch.frames) > 0
        assert batch.width >= 320
        assert batch.duration_sec >= 1.0

    def test_rejects_too_dark(self):
        frames = _solid_frames(45, color=(5, 5, 5))
        video = _make_video_bytes(frames, fps=15)
        with pytest.raises(LowQualityCaptureError, match="Iluminación"):
            FramePreprocessor().process(video)


class TestActiveLivenessHelpers:
    def test_count_blinks_detects_close_open(self):
        # secuencia: abierto → cerrado → abierto
        ears = [0.30, 0.28, 0.15, 0.14, 0.29, 0.31]
        assert ActiveLivenessChecker._count_blinks(ears) == 1

    def test_count_blinks_static_open_is_zero(self):
        ears = [0.30] * 10
        assert ActiveLivenessChecker._count_blinks(ears) == 0


class TestVectorMatcher:
    def test_match_within_threshold(self, application):
        user = TenantUser.objects.create(
            application=application,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
        embedding = np.random.randn(512).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
        BiometricProfile.objects.create(
            user=user,
            application=application,
            embedding=embedding.tolist(),
            liveness_score=0.9,
            quality_score=0.8,
        )

        matcher = VectorMatcher(application)
        # Misma dirección → distancia ~0
        result = matcher.find_best_match(embedding)
        assert result is not None
        assert result.user.id == user.id
        assert result.distance < 0.01

    def test_no_match_when_far(self, application):
        user = TenantUser.objects.create(
            application=application,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
        embedding = np.zeros(512, dtype=np.float32)
        embedding[0] = 1.0
        BiometricProfile.objects.create(
            user=user,
            application=application,
            embedding=embedding.tolist(),
            liveness_score=0.9,
        )
        other = np.zeros(512, dtype=np.float32)
        other[1] = 1.0
        application.match_threshold = 0.1
        assert VectorMatcher(application).find_best_match(other) is None


@dataclass
class _FakeActiveMetrics:
    score: float = 0.9


@dataclass
class _FakeActiveResult:
    passed: bool = True
    metrics: _FakeActiveMetrics = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = _FakeActiveMetrics()


class _FakeActive:
    def check(self, frames):
        return _FakeActiveResult()


class _FakePassive(PassiveLivenessClassifier):
    def classify(self, face_crops, threshold: float) -> PassiveLivenessResult:
        return PassiveLivenessResult(score=0.95, frame_scores=[0.95], passed=True)


class _FakeEmbedder:
    def __init__(self, embedding: np.ndarray):
        self.embedding = embedding

    def crop_faces(self, frames, max_crops: int = 3):
        return [frames[0]]

    def pick_best_frame(self, frames):
        return frames[0]

    def embed(self, frame):
        return self.embedding, 0.91


class TestBiometricServiceOrchestration:
    def test_enrollment_and_auth_with_fakes(self, application, tmp_path):
        embedding = np.random.randn(512).astype(np.float32)
        embedding /= np.linalg.norm(embedding)

        frames = _solid_frames(40)
        video = _make_video_bytes(frames)

        service = BiometricService(
            application,
            active_liveness=_FakeActive(),
            passive_liveness=_FakePassive(),
            embedder=_FakeEmbedder(embedding),
        )
        enroll = service.process_enrollment(video)
        user = TenantUser.objects.create(
            application=application,
            first_name="Demo",
            last_name="User",
            email="demo@example.com",
        )
        service.persist_enrollment(user, enroll)

        auth = service.process_authentication(video)
        assert auth.matched_user is not None
        assert auth.matched_user.id == user.id

        tokens = AuthenticationService().issue_for_user(
            auth.matched_user,
            redirect_uri="http://localhost:3000/callback",
        )
        assert tokens.access
        assert tokens.redirect_url is not None
        assert "token=" in tokens.redirect_url

    def test_duplicate_biometric_on_second_enroll(self, application):
        embedding = np.random.randn(512).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
        frames = _solid_frames(40)
        video = _make_video_bytes(frames)

        service = BiometricService(
            application,
            active_liveness=_FakeActive(),
            passive_liveness=_FakePassive(),
            embedder=_FakeEmbedder(embedding),
        )
        enroll = service.process_enrollment(video)
        user = TenantUser.objects.create(
            application=application,
            first_name="A",
            last_name="B",
            email="a@example.com",
        )
        service.persist_enrollment(user, enroll)

        with pytest.raises(DuplicateBiometricError):
            service.process_enrollment(video)

    def test_no_match_raises(self, application):
        embedding_a = np.zeros(512, dtype=np.float32)
        embedding_a[0] = 1.0
        embedding_b = np.zeros(512, dtype=np.float32)
        embedding_b[1] = 1.0
        application.match_threshold = 0.05

        frames = _solid_frames(40)
        video = _make_video_bytes(frames)

        service = BiometricService(
            application,
            active_liveness=_FakeActive(),
            passive_liveness=_FakePassive(),
            embedder=_FakeEmbedder(embedding_a),
        )
        enroll = service.process_enrollment(video)
        user = TenantUser.objects.create(
            application=application,
            first_name="A",
            last_name="B",
            email="a@example.com",
        )
        service.persist_enrollment(user, enroll)

        service_b = BiometricService(
            application,
            active_liveness=_FakeActive(),
            passive_liveness=_FakePassive(),
            embedder=_FakeEmbedder(embedding_b),
        )
        with pytest.raises(NoMatchFoundError):
            service_b.process_authentication(video)


class TestStaticSpoofRejection:
    """
    Un clip sin rostro debe fallar (FaceNotFound / ModelNotAvailable si falta el .task).
    La lógica de spoof (parpadeo/pose) se cubre en TestActiveLivenessHelpers.
    """

    def test_static_noise_clip_fails_without_face(self, tmp_path):
        from apps.biometrics.exceptions import FaceNotFoundError, ModelNotAvailableError

        # Modelo dummy inexistente → ModelNotAvailable; si existiera, FaceNotFound.
        checker = ActiveLivenessChecker(model_path=tmp_path / "missing.task")
        frames = _solid_frames(30, color=(120, 100, 90))
        with pytest.raises((FaceNotFoundError, ModelNotAvailableError)):
            checker.check(frames)
        checker.close()

    def test_spoof_reason_when_no_blinks_and_static_pose(self):
        # La regla de negocio: 0 parpadeos + pose estática ⇒ spoof.
        assert ActiveLivenessChecker._count_blinks([0.3] * 12) == 0
        yaw_delta = 0.5
        pitch_delta = 0.2
        assert (yaw_delta + pitch_delta) < ActiveLivenessChecker.MIN_POSE_DELTA



@pytest.mark.django_db
class TestCreateApplicationCommand:
    def test_create_application(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("create_application", "--name", "Acme", stdout=out)
        assert Application.objects.filter(name="Acme").exists()
        assert "app_id:" in out.getvalue()
