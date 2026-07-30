"""
Descarga pesos del pipeline biométrico fuera de git:
- MediaPipe Face Landmarker (.task)
- InsightFace buffalo_s
- MiniFASNetV2.onnx (anti-spoofing pasivo)
"""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
FACE_LANDMARKER_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"

MINIFASNET_URL = (
    "https://github.com/caijie921/Silent-Face-Anti-Spoofing/"
    "raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
)
MINIFASNET_ONNX_URLS = [
    "https://github.com/YashasSamaga/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.onnx",
]


class Command(BaseCommand):
    help = "Descarga pesos Face Landmarker, buffalo_s y MiniFASNetV2.onnx a ml_models/."

    def add_arguments(self, parser):
        parser.add_argument("--skip-insightface", action="store_true")
        parser.add_argument("--skip-minifasnet", action="store_true")
        parser.add_argument("--skip-face-landmarker", action="store_true")
        parser.add_argument("--minifasnet-url", default=None)

    def handle(self, *args, **options):
        root = Path(settings.ML_MODELS_DIR)
        root.mkdir(parents=True, exist_ok=True)
        self.stdout.write(f"ML_MODELS_DIR = {root}")

        if not options["skip_face_landmarker"]:
            self._download_file(
                root / "face_landmarker.task",
                [FACE_LANDMARKER_URL],
                label="Face Landmarker",
                expected_sha256=FACE_LANDMARKER_SHA256,
            )

        if not options["skip_insightface"]:
            self._download_insightface(root)

        if not options["skip_minifasnet"]:
            urls = ([options["minifasnet_url"]] if options["minifasnet_url"] else []) + MINIFASNET_ONNX_URLS
            ok = self._download_file(
                root / "MiniFASNetV2.onnx",
                urls,
                label="MiniFASNetV2.onnx",
                min_size=10_000,
                raise_on_fail=False,
            )
            if not ok:
                self.stdout.write(
                    self.style.WARNING(
                        "No se pudo descargar MiniFASNetV2.onnx automáticamente.\n"
                        f"  Colócalo manualmente en: {root / 'MiniFASNetV2.onnx'}\n"
                        f"  Referencia .pth: {MINIFASNET_URL}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Descarga de modelos finalizada."))

    def _download_insightface(self, root: Path) -> None:
        self.stdout.write("Descargando InsightFace buffalo_s…")
        try:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(name="buffalo_s", root=str(root), providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=-1, det_size=(640, 640))
            self.stdout.write(self.style.SUCCESS("  buffalo_s listo."))
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Fallo descargando buffalo_s: {exc}") from exc

    def _download_file(
        self,
        dest: Path,
        urls: list[str],
        *,
        label: str,
        expected_sha256: str | None = None,
        min_size: int = 1_000,
        raise_on_fail: bool = True,
    ) -> bool:
        if dest.exists() and dest.stat().st_size >= min_size:
            digest = self._sha256(dest)
            self.stdout.write(f"  {label} ya existe (sha256={digest})")
            return True

        last_error: Exception | None = None
        for url in urls:
            if not url:
                continue
            self.stdout.write(f"  Descargando {label} desde {url}")
            try:
                urllib.request.urlretrieve(url, dest)  # noqa: S310
                if dest.stat().st_size < min_size:
                    dest.unlink(missing_ok=True)
                    raise CommandError("Archivo demasiado pequeño; URL inválida.")
                digest = self._sha256(dest)
                if expected_sha256 and digest != expected_sha256:
                    dest.unlink(missing_ok=True)
                    raise CommandError(f"Checksum SHA-256 inesperado: {digest}")
                self.stdout.write(self.style.SUCCESS(f"  Guardado {dest} (sha256={digest})"))
                return True
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                dest.unlink(missing_ok=True)
                self.stdout.write(self.style.WARNING(f"  Falló: {exc}"))

        if raise_on_fail:
            raise CommandError(f"No se pudo descargar {label}: {last_error}")
        return False

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
