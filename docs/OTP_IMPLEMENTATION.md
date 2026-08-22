# OTP — Conclusiones de implementación

> Registro de lo que se implementó, decisiones tácticas y desviaciones respecto a [`OTP_VALIDATION.md`](OTP_VALIDATION.md). Cada fase se cierra aquí antes de pasar a la siguiente.  
> Para enganchar un feature nuevo (unlock, cambio de email, SMS): [`OTP_FEATURE_GUIDE.md`](OTP_FEATURE_GUIDE.md).

---

## Fase 1 — Fundación (app, modelo, hasher, canal SMTP, settings)

**Estado:** completada.

### Qué quedó

- App Django `apps.otp` registrada en `INSTALLED_APPS`.
- Modelo `OtpChallenge` (`otp_challenge`) con FK a `TenantUser` y `Application`, `purpose`/`channel` como choices (incluye purposes futuros: `step_up`, `account_unlock`, `email_change`, `reenrollment`), hashes HMAC, TTL, `verified_at` vs `consumed_at`, `attempt_count`, `invalidated_at`.
- Migración `apps/otp/migrations/0001_initial.py`.
- Hasher HMAC-SHA256 (`user_id:purpose:code` + `OTP_PEPPER`, default `SECRET_KEY`) y hash de destino normalizado en minúsculas.
- `NotificationChannel` (Protocol) + `ChannelRegistry` + `SmtpEmailChannel` (único canal activo). SMS/WhatsApp no están registrados: `get_channel("sms")` → `otp_channel_unsupported`.
- Plantillas `otp/email_verify*` y fallback genérico `otp/code*` para purposes futuros.
- Settings `OTP_*` y `EMAIL_*` en `base.py`; **console backend en `dev.py`** (el código se imprime en runserver, no sale a la red).
- `OtpError` entra al exception handler global (`{code, message, field}`) y `OtpRateLimitedError` añade cabecera `Retry-After`.
- Admin de `OtpChallenge` de solo lectura (sin alta/edición; no se usa para emitir códigos).

### Decisiones tácticas (no estaban en el diseño o lo precisan)

- El pepper del hash incluye `user_id` y `purpose` en el mensaje HMAC, no solo el código: un dump de `code_hash` no es reutilizable entre usuarios/purposes.
- `SmtpEmailChannel` captura cualquier fallo de Django mail y lo convierte en `otp_delivery_failed` (502) **sin** filtrar el mensaje SMTP ni el código. El log sí guarda el traceback, sin el código en el mensaje de log (solo `purpose`).
- Registry mutable a nivel de clase: un canal nuevo se registra con `ChannelRegistry.register(Cls)` en el `__init__` del paquete `channels`, sin tocar consumidores.
- Tests de canal usan el fixture `settings` de pytest-django (no `@override_settings` en clases pytest, que exige `SimpleTestCase`).

### Tests

`tests/unit/test_otp_foundation.py` — 13 passed (hasher, máscara `u***@dominio.com`, registry, envío locmem, fallo de entrega).

### Fuera de esta fase (siguiente)

`OtpService.issue/verify/consume`, rate limit de dominio 3/5 min, endpoints HTTP, integración con registro, frontend.

### Cómo validar en local

```bash
cd backend
pipenv run pytest tests/unit/test_otp_foundation.py -v --no-cov
```

---

## Fase 2 — OtpService (issue / verify / consume)

**Estado:** completada (código + tests escritos). Tests con `django_db` **no se ejecutaron aquí**: Docker no estaba arriba y Postgres nativo en `:5432` no tiene el rol `faceauth`. Correr cuando el `db` del compose esté healthy:

```bash
cd backend
pipenv run pytest tests/unit/test_otp_service.py tests/unit/test_otp_foundation.py -v --no-cov
```

### Qué quedó

- `apps/otp/codes.py`: `secrets.randbelow` + padding a 6 dígitos.
- `apps/otp/services.py::OtpService`:
  - `issue`: rate limit 3/5 min **antes** de invalidar; invalida activos del mismo `(user, purpose)`; persiste hash; envía por canal **fuera** de la transacción (Q5: si SMTP falla, el desafío existe y el anterior ya murió).
  - `verify`: `select_for_update`, no toca `consumed_at`, setea `verified_at`.
  - `consume`: mismas reglas + `consumed_at`; si no hubo verify previo, setea `verified_at` también (el guardado no depende de la UI).
  - 5 fallos → `invalidated_at` + `otp_locked`.
  - Purposes distintos no se pisan.
- Canal se resuelve **antes** de persistir (`get_channel`) para no quemar rate limit / invalidar si piden `sms` aún no registrado.
- Tests en `tests/unit/test_otp_service.py` (hash vs plaintext, invalidación, rate limit, verify≠consume, lock 5, TTL, replay, aislamiento por usuario).

### Decisiones tácticas

- Un código invalidado por resend, si se reingresa, se evalúa contra el **último** desafío → `otp_invalid` (no se revela que existió uno anterior). El test espera `OtpInvalidError`, no `OtpNotFoundError`.
- `OtpService` no setea `email_verified_at` ni crea usuarios: eso es del consumidor (Fase 3–4). El servicio solo habla de desafíos.
- Rate limit cuenta **todas** las emisiones en la ventana (incluidas las ya invalidadas). `retry_after` = tiempo hasta que salga la más vieja de la ventana.

### Siguiente

Endpoints `POST /api/v1/otp/request/` y `/verify/`, usuario pendiente, OpenAPI.

---

## Fase 3 — API HTTP `request` / `verify`

**Estado:** completada (código + tests escritos; mismos bloqueos de DB que Fase 2).

### Qué quedó

- `POST /api/v1/otp/request/` y `POST /api/v1/otp/verify/` (`apps.otp.urls`, montado en `/api/v1/otp/`).
- Prefijo `/api/v1/otp/` en `PUBLIC_API_PREFIXES` (el `app_id` va en el body, como auth).
- `resolve_or_create_subject`: con `email_verify` crea `TenantUser(is_active=False)` o reutiliza el pendiente y actualiza nombre/teléfono.
- API pública de **request** solo admite `purpose=email_verify` (un `account_unlock` anónimo no debe disparar mails). `verify` sigue siendo genérico por purpose.
- Throttles IP de cortesía `otp_issue` (10/min) y `otp_verify` (20/min); el tope 3/5 min sigue en el dominio.
- Tag OpenAPI `otp`. Tests en `tests/integration/test_otp_api.py`.

### Decisiones tácticas

- Sin usuario y purpose distinto de `email_verify` → `otp_not_found` genérico (no se crea pendiente para unlock).
- `first_name`/`last_name` obligatorios solo en `email_verify` (hacen falta para el alta pendiente).
- El exception handler ya serializa `OtpError`; las vistas no capturan esos errores a mano.

---

## Fase 4 — Registro consume OTP

**Estado:** completada (código + tests escritos; mismos bloqueos de DB).

### Qué quedó

- `TenantUser.email_verified_at` + migración `accounts.0002_add_email_verified_at`.
- `otp_code` obligatorio (6 dígitos) en `RegisterRequestSerializer`.
- `RegisterView` usa `ConsumesOtpMixin` (`purpose=email_verify`):
  1. Exige un `TenantUser` pendiente (si no hay → `otp_not_found`; si `is_active` → `email_taken`).
  2. Corre el pipeline biométrico **sin** persistir.
  3. En la misma transacción: `consume` → activa usuario + `email_verified_at` → `persist_enrollment`.
- Un OTP inválido no llama a `persist_enrollment` (test `test_register_wrong_otp_does_not_enroll`).
- `test_register_success` ahora pide OTP primero.

### Decisiones tácticas

- Ya no se crea el usuario en register: se reutiliza el pendiente del `request`. Eso cumple “atado al usuario” y evita una carrera de dos altas.
- `OtpError` dentro de `atomic()` hace rollback: si `persist_enrollment` fallara después de consume, el código seguiría vivo. Q6 se respeta (pipeline OK antes de consume).

---

## Fase 5 — Frontend

**Estado:** completada. `bun run test` — 24 passed.

### Qué quedó

- Wizard de registro: formulario → OTP → dashcam.
- `OtpChallengeForm` reutilizable (countdown, resend, `autoComplete=one-time-code`). El código vive solo en memoria del wizard.
- Hooks `useOtpRequest` / `useOtpVerify`; `useRegister` añade `otp_code` al `FormData`.
- Errores `otp_*` o `field=otp_code|code` devuelven al paso OTP; `email` vuelve al formulario.

### Decisiones tácticas

- No se añadió un paquete InputOTP de shadcn: un `Input` numérico de 6 caracteres basta y evita dependencia extra.
- Auto-submit al completar 6 dígitos (además del botón Validar).

---

## Fase 6 — Contrato y docs

**Estado:** completada.

- `schema.json` regenerado (`spectacular --fail-on-warn --validate`).
- Tipos TS con `bun run generate:api`.
- Actualizados `ARCHITECTURE.md`, `MASTER_PLAN.md` (Fase 9), `INTEGRATION_GUIDE.md` §4.4, `README.md`.

### Pendiente operativo (no es código)

1. Levantar Postgres (`docker compose up -d db`) y `pipenv run python manage.py migrate`.
2. Correr `pytest tests/unit/test_otp_*.py tests/integration/test_otp_api.py tests/integration/test_auth_api.py`.
3. Probar registro: el código aparece en la consola del backend (dev).



