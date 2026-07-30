"""
Prueba de carga de VectorMatcher con volumen simulado por tenant.
"""
from __future__ import annotations

import statistics
import time

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import BiometricProfile, TenantUser
from apps.biometrics.services.vector_matcher import VectorMatcher
from apps.tenants.models import Application


def _rand_embedding(rng: np.random.Generator) -> np.ndarray:
    v = rng.standard_normal(512).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


class Command(BaseCommand):
    help = "Inserta N embeddings sintéticos y mide latencia de find_best_match."

    def add_arguments(self, parser):
        parser.add_argument("--app-id", required=True)
        parser.add_argument(
            "--count",
            type=int,
            default=10_000,
            help="Perfiles a insertar (prueba con 10000; 100000 puede tardar).",
        )
        parser.add_argument("--queries", type=int, default=50)
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Borra los usuarios sintéticos creados por este comando al final.",
        )
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        try:
            app = Application.objects.get(app_id=options["app_id"])
        except Application.DoesNotExist as exc:
            raise CommandError("Application no encontrada.") from exc

        count = options["count"]
        queries = options["queries"]
        rng = np.random.default_rng(options["seed"])
        tag = f"bench_vector_{options['seed']}"

        self.stdout.write(f"Insertando {count} perfiles en {app.app_id}…")
        batch_users: list[TenantUser] = []
        for i in range(count):
            batch_users.append(
                TenantUser(
                    application=app,
                    first_name="Bench",
                    last_name=str(i),
                    email=f"{tag}_{i}@bench.local",
                    phone="",
                )
            )
            if len(batch_users) >= 500 or i == count - 1:
                created = TenantUser.objects.bulk_create(batch_users)
                profiles = [
                    BiometricProfile(
                        user=u,
                        application=app,
                        embedding=_rand_embedding(rng).tolist(),
                        liveness_score=0.99,
                        quality_score=0.9,
                        is_active=True,
                    )
                    for u in created
                ]
                BiometricProfile.objects.bulk_create(profiles)
                batch_users = []
                if (i + 1) % 2000 == 0 or i == count - 1:
                    self.stdout.write(f"  … {i + 1}/{count}")

        total = BiometricProfile.objects.filter(application=app, is_active=True).count()
        self.stdout.write(f"Perfiles activos en tenant: {total}")

        matcher = VectorMatcher(application=app)
        times = []
        for _ in range(queries):
            q = _rand_embedding(rng)
            t0 = time.perf_counter()
            matcher.find_best_match(q)
            times.append(time.perf_counter() - t0)

        mean = statistics.mean(times)
        p50 = statistics.median(times)
        p95 = sorted(times)[max(0, int(len(times) * 0.95) - 1)]
        self.stdout.write(
            f"find_best_match n={queries} mean={mean*1000:.2f}ms "
            f"p50={p50*1000:.2f}ms p95={p95*1000:.2f}ms"
        )

        if options["cleanup"]:
            deleted, _ = TenantUser.objects.filter(
                application=app, email__startswith=f"{tag}_"
            ).delete()
            self.stdout.write(self.style.WARNING(f"Cleanup: {deleted} objetos eliminados."))
