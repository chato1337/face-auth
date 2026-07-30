# Operaciones — Face-Auth

## Agregar un nuevo tenant

```bash
cd backend
pipenv run python manage.py create_application \
  --name "Mi App" \
  --redirect-uri "https://mi-app.example/callback" \
  --liveness-threshold 0.85 \
  --match-threshold 0.42
```

Guarda `app_id` y `api_key` en el gestor de secretos del cliente. El frontend abre:

`https://face-auth.example/login?app_id=<app_id>&redirect_uri=<uri_whitelisteada>`

Alternativa: Django admin → Applications.

## Rotar `api_key`

```bash
pipenv run python manage.py rotate_api_key --app-id app_XXX --yes
```

La clave anterior queda inválida de inmediato. Entrega la nueva al cliente por canal seguro. También disponible como acción masiva en el admin.

## Rotar / actualizar modelos ONNX

1. Descarga nueva versión a un directorio staging:
   ```bash
   pipenv run python manage.py download_ml_models
   ```
2. Verifica checksums en `apps/biometrics/ml_models/README.md`.
3. Sustituye `MiniFASNetV2.onnx` / `face_landmarker.task` / pesos `buffalo_s`.
4. Reinicia workers (gunicorn) para vaciar el `ModelPool` en memoria.
5. Corre smoke:
   ```bash
   pipenv run python manage.py demo_biometric_flow --app-id … --enroll-video … --auth-video …
   pipenv run python manage.py evaluate_liveness --app-id … --dataset …
   ```

## Benchmarks

```bash
# Latencia pipeline (presupuesto default 8s p50)
pipenv run python manage.py benchmark_pipeline \
  --app-id app_XXX --video /path/clip.mp4 --runs 5 --mock-passive

# Carga vectorial HNSW (10k perfiles)
pipenv run python manage.py benchmark_vector_search \
  --app-id app_XXX --count 10000 --queries 50 --cleanup
```

## Runbook — incidentes comunes

### Falsos rechazos masivos (FRR ↑)

1. Revisar `evaluate_liveness` reciente y umbral del tenant.
2. Verificar iluminación / guía UX del frontend (cuenta regresiva, óvalo).
3. Confirmar que los pesos ML no se corrompieron (checksum).
4. Temporal: bajar `liveness_threshold` del tenant 0.05 y monitorear FAR.

### Caída de latencia (p50/p95 ↑)

1. `benchmark_pipeline` en el host afectado.
2. Confirmar que `ModelPool` no se reinicia por worker recycle excesivo.
3. Revisar CPU steal / contención Docker; subir workers solo si hay cores.
4. Revisar tamaño de índice: `benchmark_vector_search` a escala del tenant.

### Rate limit 429 inesperado

- Default: `BIOMETRIC_AUTH_THROTTLE=30/min` por `app_id` + IP.
- Ajustar en `.env` y reiniciar. En multi-worker, migrar cache a Redis.

### Redirect SSO fallido

- `redirect_uri` debe coincidir **exactamente** (tras normalización) con una entrada de `Application.redirect_uris`.
- Prefijos o paths extra → `400 invalid_redirect_uri`.
