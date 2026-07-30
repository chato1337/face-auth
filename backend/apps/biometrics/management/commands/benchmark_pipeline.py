"""
Benchmark de latencia end-to-end del pipeline biométrico (CPU).

Objetivo de referencia (Fase 5): clip 2–3 s procesado en < 8 s en CPU de laptop
moderna (ajustable con --budget-seconds).
"""
from __future__ import annotations

import statistics
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.biometrics.services import BiometricService
from apps.biometrics.services.model_pool import ModelPool
from apps.tenants.models import Application


class Command(BaseCommand):
    help = "Mide latencia end-to-end de process_enrollment / process_authentication."

    def add_arguments(self, parser):
        parser.add_argument("--app-id", required=True)
        parser.add_argument("--video", required=True, help="Ruta a clip mp4/webm de 2–3 s.")
        parser.add_argument("--runs", type=int, default=5)
        parser.add_argument("--warmup", type=int, default=1)
        parser.add_argument(
            "--mode",
            choices=("enroll", "auth", "both"),
            default="enroll",
        )
        parser.add_argument(
            "--budget-seconds",
            type=float,
            default=8.0,
            help="Presupuesto de latencia p50 (default 8s CPU).",
        )
        parser.add_argument(
            "--mock-passive",
            action="store_true",
            help="Usa clasificador pasivo mock (útil sin MiniFASNetV2.onnx).",
        )

    def handle(self, *args, **options):
        try:
            app = Application.objects.get(app_id=options["app_id"])
        except Application.DoesNotExist as exc:
            raise CommandError("Application no encontrada.") from exc

        path = Path(options["video"])
        if not path.is_file():
            raise CommandError(f"Video no encontrado: {path}")
        video_bytes = path.read_bytes()

        ModelPool.reset_for_tests()
        kwargs = {}
        if options["mock_passive"]:
            from unittest.mock import MagicMock

            from apps.biometrics.services.liveness_passive import PassiveLivenessResult

            mock = MagicMock()
            mock.classify.return_value = PassiveLivenessResult(
                score=0.99, frame_scores=[0.99], passed=True
            )
            kwargs["passive_liveness"] = mock

        service = BiometricService(app, **kwargs)
        mode = options["mode"]
        runs = options["runs"]
        warmup = options["warmup"]
        budget = options["budget_seconds"]

        def _timed(fn):
            times = []
            for i in range(warmup + runs):
                t0 = time.perf_counter()
                fn()
                elapsed = time.perf_counter() - t0
                if i >= warmup:
                    times.append(elapsed)
            return times

        results = {}
        if mode in ("enroll", "both"):
            results["enroll"] = _timed(lambda: service.process_enrollment(video_bytes))
        if mode in ("auth", "both"):
            # auth requiere perfiles; si no hay match lanza — para bench puro usar enroll.
            results["auth"] = _timed(lambda: service.process_authentication(video_bytes))

        ok = True
        for name, times in results.items():
            p50 = statistics.median(times)
            p95 = sorted(times)[max(0, int(len(times) * 0.95) - 1)]
            mean = statistics.mean(times)
            self.stdout.write(f"[{name}] n={len(times)} mean={mean:.3f}s p50={p50:.3f}s p95={p95:.3f}s")
            if p50 > budget:
                ok = False
                self.stdout.write(
                    self.style.ERROR(f"  FAIL presupuesto: p50 {p50:.3f}s > {budget:.3f}s")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  OK presupuesto: p50 {p50:.3f}s ≤ {budget:.3f}s")
                )

        if not ok:
            raise CommandError("Benchmark fuera de presupuesto de latencia.")
