# Face-Auth Frontend

Vite + React + TypeScript. Flujos de login y registro biométrico (SSO hosted) y panel admin.

## Arranque

```bash
bun install
# Configura FRONTEND_PORT y VITE_API_BASE_URL en el `.env` de la raíz del monorepo
bun run dev
```

Variables (`.env` raíz; Vite usa `envDir` del monorepo):

| Variable | Default | Uso |
|----------|---------|-----|
| `FRONTEND_PORT` | `5173` | Puerto del servidor Vite (`strictPort`) |
| `VITE_API_BASE_URL` | `http://localhost:8000` | URL completa del API vista desde el navegador (host + puerto) |

Si cambias el host (p. ej. IP LAN), edita `VITE_API_BASE_URL` entero — no solo `BACKEND_PORT` — y reinicia Vite.

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
