from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import Application


class Command(BaseCommand):
    help = (
        "Rota la api_key de una Application. La clave anterior queda inválida de inmediato. "
        "Muestra la nueva clave una sola vez (guárdala en el gestor de secretos del tenant)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--app-id", required=True, help="app_id del tenant.")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirma la rotación sin prompt interactivo.",
        )

    def handle(self, *args, **options):
        app_id = options["app_id"].strip()
        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist as exc:
            raise CommandError(f"Application no encontrada: {app_id}") from exc

        if not options["yes"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Esto invalidará la api_key actual de '{app.name}' ({app.app_id})."
                )
            )
            confirm = input("Escribe 'rotate' para continuar: ").strip()
            if confirm != "rotate":
                raise CommandError("Rotación cancelada.")

        new_key = app.rotate_api_key()
        self.stdout.write(self.style.SUCCESS("api_key rotada."))
        self.stdout.write(f"  app_id:  {app.app_id}")
        self.stdout.write(f"  api_key: {new_key}")
        self.stdout.write(f"  rotated_at: {app.api_key_rotated_at.isoformat()}")
        self.stdout.write(
            self.style.WARNING("Guarda la nueva api_key ahora; no se volverá a mostrar.")
        )
