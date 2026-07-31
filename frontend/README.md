# Face-Auth Frontend

Vite + React + TypeScript. Flujos de login y registro biométrico (SSO hosted) y panel admin.

## Arranque

```bash
bun install
cp .env.example .env
# Ajusta FRONTEND_PORT y VITE_API_BASE_URL si el backend no usa el puerto 8000
bun run dev
```

Variables relevantes (`frontend/.env`):

| Variable | Default | Uso |
|----------|---------|-----|
| `FRONTEND_PORT` | `5173` | Puerto del servidor Vite (`strictPort`) |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL del API (debe coincidir con `BACKEND_PORT`) |

En Docker Compose estos valores se inyectan desde el `.env` raíz (`FRONTEND_PORT` / `BACKEND_PORT`).

Abrir con tenant válido, por ejemplo:

- http://localhost:5173/login?app_id=app_XXXX
- http://localhost:5173/register?app_id=app_XXXX&redirect_uri=http://localhost:3000/callback

## Scripts

| Comando | Descripción |
|---------|-------------|
| `bun run dev` | Servidor de desarrollo |
| `bun run build` | Typecheck + build producción |
| `bun run generate:api` | Regenera `src/api/generated/schema.d.ts` desde `backend/schema.json` |
| `bun run test` | Vitest (CameraCapture, login/registro) |
| `bun run lint` | Oxlint |

Tras cambios en el contrato OpenAPI del backend:

```bash
cd ../backend
pipenv run python manage.py spectacular --file schema.json --format openapi-json --fail-on-warn --validate
cd ../frontend
bun run generate:api
```
