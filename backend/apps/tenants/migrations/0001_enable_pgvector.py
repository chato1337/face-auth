"""
Migración inicial: habilita la extensión pgvector en PostgreSQL.

Debe ejecutarse antes de cualquier migración que declare VectorField.
Los modelos de dominio (Application, TenantUser, BiometricProfile) llegan en Fase 2.
"""
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        CreateExtension("vector"),
    ]
