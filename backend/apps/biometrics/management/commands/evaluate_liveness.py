"""
Evalúa FAR/FRR del pipeline de liveness sobre un dataset etiquetado.

Estructura esperada (ver docs/datasets/README.md):

    dataset/
      genuine/   # clips de rostros reales vivos
      spoof/     # foto impresa, pantalla, video replay, etc.

Salida: tasas FAR/FRR + recomendaciones de umbral.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from unittest.mock import MagicMock

from django.core.management.base import BaseCommand, CommandError

from apps.biometrics.exceptions import BiometricPipelineError, DuplicateBiometricError
from apps.biometrics.services.biometric_service import BiometricService
from apps.biometrics.services.liveness_passive import PassiveLivenessResult
from apps.tenants.models import Application


VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".avi"}


@dataclass
class EvalMetrics:
    genuine_total: int
    spoof_total: int
    genuine_accepted: int
    spoof_accepted: int
    frr: float
    far: float
    liveness_threshold: float
    notes: str


class Command(BaseCommand):
    help = "Calcula FAR/FRR de liveness sobre carpetas genuine/ y spoof/."

    def add_arguments(self, parser):
        parser.add_argument("--app-id", required=True)
        parser.add_argument("--dataset", required=True, type=Path)
        parser.add_argument(
            "--threshold",
            type=float,
            default=None,
            help="Override de liveness_threshold del tenant.",
        )
        parser.add_argument(
            "--mock-passive",
            action="store_true",
            help="Solo evalúa liveness activo (pasivo mockeado a 1.0).",
        )
        parser.add_argument("--json-out", type=Path, default=None)

    def handle(self, *args, **options):
        try:
            app = Application.objects.get(app_id=options["app_id"])
        except Application.DoesNotExist as exc:
            raise CommandError("Application no encontrada.") from exc

        root: Path = options["dataset"]
        genuine_dir = root / "genuine"
        spoof_dir = root / "spoof"
        if not genuine_dir.is_dir() or not spoof_dir.is_dir():
            raise CommandError(
                f"Dataset inválido. Se esperan {genuine_dir} y {spoof_dir}. "
                "Ver docs/datasets/README.md"
            )

        if options["threshold"] is not None:
            app.liveness_threshold = options["threshold"]

        kwargs = {}
        if options["mock_passive"]:
            mock = MagicMock()
            mock.classify.return_value = PassiveLivenessResult(
                score=1.0, frame_scores=[1.0], passed=True
            )
            kwargs["passive_liveness"] = mock

        service = BiometricService(app, **kwargs)

        genuine_files = _list_videos(genuine_dir)
        spoof_files = _list_videos(spoof_dir)
        if not genuine_files or not spoof_files:
            raise CommandError("Se requieren videos en genuine/ y spoof/.")

        genuine_accepted = 0
        for path in genuine_files:
            if _liveness_passes(service, path):
                genuine_accepted += 1

        spoof_accepted = 0
        for path in spoof_files:
            if _liveness_passes(service, path):
                spoof_accepted += 1

        genuine_total = len(genuine_files)
        spoof_total = len(spoof_files)
        frr = 1.0 - (genuine_accepted / genuine_total)
        far = spoof_accepted / spoof_total

        metrics = EvalMetrics(
            genuine_total=genuine_total,
            spoof_total=spoof_total,
            genuine_accepted=genuine_accepted,
            spoof_accepted=spoof_accepted,
            frr=frr,
            far=far,
            liveness_threshold=app.liveness_threshold,
            notes=(
                "Objetivos orientativos pre-producción: FAR ≤ 0.05, FRR ≤ 0.10 "
                "en dataset controlado. Ajustar liveness_threshold / match_threshold por tenant."
            ),
        )

        self.stdout.write(json.dumps(asdict(metrics), indent=2))
        self.stdout.write(
            self.style.SUCCESS(
                f"FAR={far:.3f} ({spoof_accepted}/{spoof_total} spoofs aceptados)  "
                f"FRR={frr:.3f} ({genuine_total - genuine_accepted}/{genuine_total} genuinos rechazados)"
            )
        )
        if options["json_out"]:
            options["json_out"].write_text(json.dumps(asdict(metrics), indent=2))
            self.stdout.write(f"Escrito: {options['json_out']}")


def _list_videos(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)


def _liveness_passes(service: BiometricService, path: Path) -> bool:
    """
    Considera 'aceptado por liveness' si el pipeline llega al menos al embedding
    (enroll) o falla solo por duplicado/match — no por spoof/calidad.
    """
    try:
        service.process_enrollment(path.read_bytes())
        return True
    except DuplicateBiometricError:
        return True
    except BiometricPipelineError:
        return False
