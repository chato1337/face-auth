# Datasets de evaluación (Fase 5)

Estructura para `evaluate_liveness` y medición FAR/FRR:

```
docs/datasets/
  sample/                 # opcional, no versionar clips reales con PII
    genuine/              # rostros reales vivos (parpadeo + leve movimiento)
      person_a_01.mp4
    spoof/
      print_photo_01.mp4          # foto impresa
      screen_phone_01.mp4         # foto en pantalla de móvil
      screen_monitor_01.mp4       # foto/video en monitor
      replay_video_01.mp4         # video pregrabado reproducido
      mask_or_deepfake_01.mp4     # si es factible
  adverse/                # condiciones adversas (documentación / labs)
    low_light/
    backlight/
    partial_occlusion/
    multi_face/
```

> **No subas videos con rostros reales a git.** Usa clips sintéticos o datos internos con consentimiento. Los pesos y datasets con PII van fuera del control de versiones.

## Cómo evaluar

```bash
cd backend
pipenv run python manage.py evaluate_liveness \
  --app-id app_XXX \
  --dataset ../docs/datasets/sample \
  --json-out /tmp/far_frr.json

# Solo liveness activo (sin MiniFASNet):
pipenv run python manage.py evaluate_liveness \
  --app-id app_XXX \
  --dataset ../docs/datasets/sample \
  --mock-passive
```

## Objetivos orientativos

| Métrica | Objetivo pre-prod | Notas |
|---------|-------------------|-------|
| FAR (spoofs aceptados) | ≤ 0.05 | Ajustar `liveness_threshold` ↑ si FAR alto |
| FRR (genuinos rechazados) | ≤ 0.10 | Bajar umbral o mejorar guía UX de captura |
| Latencia p50 pipeline | ≤ 8 s (CPU laptop) | Ver `benchmark_pipeline` |

Umbrales por defecto del servicio: `liveness_threshold=0.85`, `match_threshold=0.42` (sobreescritos por Application).
