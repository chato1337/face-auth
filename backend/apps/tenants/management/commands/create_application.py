from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import Application


class Command(BaseCommand):
    help = "Crea una Application (tenant) de prueba y muestra app_id / api_key."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Nombre visible de la aplicación.")
        parser.add_argument(
            "--redirect-uri",
            action="append",
            dest="redirect_uris",
            default=[],
            help="URI de redirect permitida (repetible).",
        )
        parser.add_argument(
            "--liveness-threshold",
            type=float,
            default=0.85,
            help="Umbral de liveness pasivo (default 0.85).",
        )
        parser.add_argument(
            "--match-threshold",
            type=float,
            default=0.42,
            help="Umbral de distancia coseno (default 0.42).",
        )

    def handle(self, *args, **options):
        name = options["name"].strip()
        if not name:
            raise CommandError("--name no puede estar vacío.")

        app = Application.objects.create(
            name=name,
            redirect_uris=options["redirect_uris"] or ["http://localhost:3000/callback"],
            liveness_threshold=options["liveness_threshold"],
            match_threshold=options["match_threshold"],
        )
        self.stdout.write(self.style.SUCCESS(f"Application creada: {app.name}"))
        self.stdout.write(f"  app_id:  {app.app_id}")
        self.stdout.write(f"  api_key: {app.api_key}")
        self.stdout.write(f"  redirect_uris: {app.redirect_uris}")
