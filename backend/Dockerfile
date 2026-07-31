# syntax=docker/dockerfile:1
# Backend Face-Auth — Django + pipeline biométrico (pipenv).
#
# Dependencias de sistema necesarias para mediapipe / insightface / opencv:
#   - cmake, build-essential (compilación de extensiones nativas)
#   - libgl1, libglib2.0-0 (OpenCV headless / MediaPipe)
#   - libgomp1 (OpenMP, usado por onnxruntime/insightface)
#
# Se instala con `pipenv install --deploy --ignore-pipfile --system` para que el
# bind-mount de ./backend:/app en desarrollo no pise el virtualenv de la imagen.
#
# Los pesos ML (gitignored) se descargan en build y de nuevo en el entrypoint
# (idempotente): el bind-mount de compose pisa /app y vacía ml_models/ en hosts frescos.
FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIPENV_YES=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip pipenv

COPY Pipfile Pipfile.lock ./

# Solo runtime ([packages]); sin [dev-packages]; al system site-packages
RUN pipenv install --deploy --ignore-pipfile --system \
    && pip uninstall -y pipenv virtualenv || true

COPY . .
RUN chmod +x /app/entrypoint.sh

# Mínimo para que `download_ml_models` pueda bootstrappear Django en build.
ENV DJANGO_SETTINGS_MODULE=config.settings.dev \
    SECRET_KEY=build-only-not-for-runtime \
    DEBUG=True \
    ALLOWED_HOSTS=localhost \
    CORS_ALLOWED_ORIGINS=http://localhost:5173 \
    BACKEND_PORT=8000

RUN python manage.py download_ml_models

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${BACKEND_PORT:-8000} --workers 2"]
