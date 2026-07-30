"""
Búsqueda vectorial por distancia coseno con pgvector, filtrada por Application.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pgvector.django import CosineDistance

from apps.accounts.models import BiometricProfile, TenantUser
from apps.tenants.models import Application


@dataclass(frozen=True)
class MatchResult:
    user: TenantUser
    profile: BiometricProfile
    distance: float


class VectorMatcher:
    def __init__(self, application: Application):
        self.application = application

    def find_best_match(self, embedding: np.ndarray) -> MatchResult | None:
        vector = embedding.astype(np.float32).tolist()
        qs = (
            BiometricProfile.objects.filter(
                application=self.application,
                is_active=True,
            )
            .select_related("user")
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")[:1]
        )
        profile = qs.first()
        if profile is None:
            return None
        distance = float(profile.distance)
        if distance > self.application.match_threshold:
            return None
        if not profile.user.is_active:
            return None
        return MatchResult(user=profile.user, profile=profile, distance=distance)

    def find_duplicate(
        self,
        embedding: np.ndarray,
        *,
        threshold: float | None = None,
    ) -> MatchResult | None:
        """Detecta si el rostro ya está enrolado en este tenant (registro)."""
        original = self.application.match_threshold
        try:
            if threshold is not None:
                self.application.match_threshold = threshold
            return self.find_best_match(embedding)
        finally:
            self.application.match_threshold = original
