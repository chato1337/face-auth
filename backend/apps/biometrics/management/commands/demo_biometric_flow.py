"""
Demo / aceptación Fase 2: enroll + authenticate con videos locales.

Ejemplo:
  pipenv run python manage.py demo_biometric_flow \\
    --app-id app_xxx \\
    --email demo@example.com \\
    --enroll-video /path/enroll.mp4 \\
    --auth-video /path/auth.mp4 \\
    --spoof-video /path/static_photo.mp4
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import TenantUser
from apps.biometrics.exceptions import BiometricPipelineError, SpoofDetectedError
from apps.biometrics.services import BiometricService
from apps.biometrics.services.liveness_passive import PassiveLivenessClassifier, PassiveLivenessResult
from apps.tenants.models import Application
from apps.authentication.services import AuthenticationService


class _AlwaysPassPassive(PassiveLivenessClassifier):
    """Útil si aún no está MiniFASNetV2.onnx (solo para demos locales)."""

    def classify(self, face_crops, threshold: float) -> PassiveLivenessResult:
        return PassiveLivenessResult(score=max(threshold, 0.99), frame_scores=[0.99], passed=True)


class Command(BaseCommand):
    help = "Enroll + auth biométrico de punta a punta (sin HTTP)."

    def add_arguments(self, parser):
        parser.add_argument("--app-id", required=True)
        parser.add_argument("--email", default="demo@face-auth.local")
        parser.add_argument("--first-name", default="Demo")
        parser.add_argument("--last-name", default="User")
        parser.add_argument("--enroll-video", required=True, type=Path)
        parser.add_argument("--auth-video", required=True, type=Path)
        parser.add_argument("--spoof-video", type=Path, default=None)
        parser.add_argument(
            "--mock-passive",
            action="store_true",
            help="Salta MiniFASNet (siempre pasa liveness pasivo).",
        )

    def handle(self, *args, **options):
        try:
            application = Application.objects.get(app_id=options["app_id"])
        except Application.DoesNotExist as exc:
            raise CommandError(f"Application no encontrada: {options['app_id']}") from exc

        enroll_bytes = self._read(options["enroll_video"])
        auth_bytes = self._read(options["auth_video"])

        passive = _AlwaysPassPassive() if options["mock_passive"] else None
        service = BiometricService(application, passive_liveness=passive)

        self.stdout.write("→ Enrolamiento…")
        try:
            enroll = service.process_enrollment(enroll_bytes)
        except BiometricPipelineError as exc:
            raise CommandError(f"Enrolamiento falló: {exc}") from exc

        with transaction.atomic():
            user, _created = TenantUser.objects.get_or_create(
                application=application,
                email=options["email"],
                defaults={
                    "first_name": options["first_name"],
                    "last_name": options["last_name"],
                },
            )
            profile = service.persist_enrollment(user, enroll)

        self.stdout.write(self.style.SUCCESS(f"  Usuario {user.email} / profile {profile.id}"))
        self.stdout.write(f"  liveness passive={enroll.liveness.passive_score:.3f} quality={enroll.quality_score:.3f}")

        self.stdout.write("→ Autenticación…")
        try:
            auth = service.process_authentication(auth_bytes)
        except BiometricPipelineError as exc:
            raise CommandError(f"Autenticación falló: {exc}") from exc

        assert auth.matched_user is not None
        self.stdout.write(
            self.style.SUCCESS(
                f"  Match OK user={auth.matched_user.email} distance={auth.distance:.4f}"
            )
        )

        tokens = AuthenticationService().issue_for_user(
            auth.matched_user,
            redirect_uri=(application.redirect_uris or [None])[0],
        )
        self.stdout.write(f"  access token (trunc): {tokens.access[:48]}…")
        if tokens.redirect_url:
            self.stdout.write(f"  redirect_url: {tokens.redirect_url[:120]}…")

        if options["spoof_video"]:
            self.stdout.write("→ Spoof (foto estática)…")
            spoof_bytes = self._read(options["spoof_video"])
            try:
                service.process_authentication(spoof_bytes)
                raise CommandError("Se esperaba rechazo por liveness, pero el spoof pasó.")
            except SpoofDetectedError as exc:
                self.stdout.write(self.style.SUCCESS(f"  Rechazado correctamente: {exc}"))
            except BiometricPipelineError as exc:
                self.stdout.write(self.style.SUCCESS(f"  Rechazado ({exc.code}): {exc}"))

        self.stdout.write(self.style.SUCCESS("Demo biométrica completada."))

    @staticmethod
    def _read(path: Path) -> bytes:
        if not path.exists():
            raise CommandError(f"Archivo no encontrado: {path}")
        return path.read_bytes()
