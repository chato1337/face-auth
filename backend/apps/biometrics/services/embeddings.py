"""
Extracción de embeddings faciales con InsightFace buffalo_s (512-d, L2-norm).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from django.conf import settings

from apps.biometrics.exceptions import FaceNotFoundError, ModelNotAvailableError


class FaceEmbedder:
    MODEL_NAME = "buffalo_s"
    EMBEDDING_DIM = 512

    def __init__(self, root: Path | None = None):
        self.root = root or Path(settings.ML_MODELS_DIR)
        self._app = None

    def _ensure_app(self):
        if self._app is not None:
            return
        try:
            from insightface.app import FaceAnalysis
        except ImportError as exc:
            raise ModelNotAvailableError("insightface no está instalado.", field=None) from exc

        # InsightFace descarga buffalo_s bajo root si no existe.
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            app = FaceAnalysis(
                name=self.MODEL_NAME,
                root=str(self.root),
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(640, 640))
        except Exception as exc:  # noqa: BLE001 — superficie como error de modelo
            raise ModelNotAvailableError(
                f"No se pudo cargar InsightFace {self.MODEL_NAME}: {exc}. "
                "Ejecuta: pipenv run python manage.py download_ml_models",
                field=None,
            ) from exc
        self._app = app

    def embed(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        """
        Retorna (embedding float32[512] L2-normalizado, det_score).
        """
        self._ensure_app()
        assert self._app is not None

        faces = self._app.get(frame_bgr)
        if not faces:
            raise FaceNotFoundError("No se pudo alinear/extraer el rostro para embedding.", field="video")

        # Elegir el rostro de mayor score de detección
        face = max(faces, key=lambda f: float(getattr(f, "det_score", 0.0)))
        embedding = np.asarray(face.embedding, dtype=np.float32).reshape(-1)
        if embedding.shape[0] != self.EMBEDDING_DIM:
            raise FaceNotFoundError(
                f"Embedding inesperado de dimensión {embedding.shape[0]} (esperado {self.EMBEDDING_DIM}).",
                field="video",
            )
        norm = np.linalg.norm(embedding)
        if norm < 1e-8:
            raise FaceNotFoundError("Embedding degenerado (norma ~0).", field="video")
        embedding = embedding / norm
        return embedding, float(getattr(face, "det_score", 0.0))

    def pick_best_frame(self, frames: list[np.ndarray]) -> np.ndarray:
        """Selecciona el frame de mayor nitidez (varianza del Laplaciano)."""
        if not frames:
            raise FaceNotFoundError("Sin frames para seleccionar.", field="video")
        best = frames[0]
        best_score = -1.0
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if score > best_score:
                best_score = score
                best = frame
        return best

    def crop_faces(self, frames: list[np.ndarray], max_crops: int = 3) -> list[np.ndarray]:
        """Recorta rostros con el detector de InsightFace para liveness pasivo."""
        self._ensure_app()
        assert self._app is not None
        crops: list[tuple[float, np.ndarray]] = []
        for frame in frames:
            faces = self._app.get(frame)
            for face in faces:
                bbox = getattr(face, "bbox", None)
                if bbox is None:
                    continue
                x1, y1, x2, y2 = [int(v) for v in bbox]
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                crop = frame[y1:y2, x1:x2]
                crops.append((float(getattr(face, "det_score", 0.0)), crop))
        if not crops:
            raise FaceNotFoundError("No se pudieron recortar rostros para liveness pasivo.", field="video")
        crops.sort(key=lambda t: t[0], reverse=True)
        return [c for _, c in crops[:max_crops]]
