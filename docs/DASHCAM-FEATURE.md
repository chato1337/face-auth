**Actúa como un Frontend Senior Engineer y Experto en Computer Vision en el navegador.**

**Contexto del Proyecto:**
Ya tenemos implementado un sistema de autenticación biométrica (React en el frontend, Django en el backend). Actualmente, el usuario debe presionar un botón para grabar su video y enviarlo. El backend ya tiene implementada una arquitectura "Zero-Trust" que valida el liveness (anti-spoofing) y extrae el embedding del video recibido.

**El Feature Request:**
Quiero refactorizar la experiencia de usuario (UX) en el frontend. Vamos a eliminar el botón manual de "Grabar" e implementar un patrón de "Dashcam" (captura pasiva) que se dispare automáticamente cuando el usuario parpadee.

**Flujo de UX y Lógica Requerida:**
1. **Inicialización:** Al entrar a la vista, se solicita permiso y se enciende la cámara. Se muestra el stream de video con un "óvalo" o marco guía superpuesto.
2. **Detección Pasiva:** Utilizando `@mediapipe/tasks-vision` (Face Landmarker) en el navegador, evalúa en tiempo real si hay un rostro alineado dentro del marco.
3. **Grabación en Espera:** Una vez el rostro está alineado, se inicia internamente la grabación usando la API `MediaRecorder`. La interfaz debe mostrar un mensaje: *"Rostro detectado. Parpadee para confirmar"*.
4. **Trigger (El Parpadeo):** El modelo de MediaPipe en el cliente debe calcular constantemente el EAR (Eye Aspect Ratio) de ambos ojos. Cuando detecte una caída en el EAR (un parpadeo claro), se detiene el `MediaRecorder`.
5. **Auto-Envío:** Se toma el archivo de video generado (los últimos ~2 o 3 segundos de grabación), y se envía automáticamente vía `multipart/form-data` al endpoint existente del backend.
6. **Manejo de Errores:** Si el backend rechaza el video (ej. mala iluminación o spoofing detectado), la interfaz muestra un Toast/Alerta con el error y reinicia automáticamente el flujo desde el paso 2, sin recargar la página.

**Requerimientos Técnicos:**
* **Tecnologías:** React, TypeScript, `@mediapipe/tasks-vision` (WebAssembly), `MediaRecorder` API nativa, TanStack Query (para la mutación al backend).
* **Rendimiento:** La inferencia de MediaPipe debe correr usando `requestAnimationFrame` y preferiblemente no bloquear el hilo principal de React.
* **Seguridad:** Ten en cuenta que el cliente **solo** usa MediaPipe como un *trigger de conveniencia (UX)*. El backend seguirá realizando la validación biométrica real.

**Tu tarea inicial:**
No me des todo el componente completo de React todavía. Para empezar, divídelo en las siguientes partes manejables:

1. **Custom Hook `useFaceLandmarker`:** Escribe el código de un custom hook de React que inicialice MediaPipe Face Landmarker eficientemente.
2. **Lógica de EAR (Eye Aspect Ratio):** Escribe la función matemática en TypeScript que reciba los landmarks de MediaPipe y detecte un parpadeo.
3. **Custom Hook `useDashcamRecorder`:** Escribe un hook que maneje la lógica de inicializar la cámara, el `MediaRecorder`, arrancar cuando se lo indiquen y devolver el `Blob` de video cuando se dispare el evento de stop.

Entrégame esto primero para revisarlo. Una vez aprobado, te pediré que unas todas las piezas en el componente visual final.

---

## Estado de implementación — conclusiones (2026-07-30)

**Implementado y verificado** (tests: 30 en verde; `tsc`, `oxlint` y build de producción sin errores). Detalle por fase en [`MASTER_PLAN.md` §Fase 7](MASTER_PLAN.md).

**Qué se construyó** (todo en `frontend/src/components/camera/`):

| Pieza | Archivo | Decisión clave |
|---|---|---|
| Hook MediaPipe | `useFaceLandmarker.ts` | Singleton de sesión (no re-inicializa en cada reintento), fallback GPU→CPU, import dinámico (chunk lazy ~153 kB), assets por CDN pinneado a `@mediapipe/tasks-vision@1.0.0`. |
| Lógica EAR/parpadeo/alineación | `faceMetrics.ts` | EAR clásico con corrección de aspect ratio; máquina de estados con histéresis (0.20/0.25) y mínimo 2 frames cerrados; dispara al **reabrir** los ojos para que el clip contenga el ciclo completo. Alineación por bounding box con hints (`céntrate`/`acércate`/`alékate`). |
| Utilidades de cámara | `videoRecorder.ts` | `requestCameraStream(facingMode)` (`"user"` por defecto), `countVideoInputDevices()` (`enumerateDevices` + filtro `videoinput`) y `oppositeFacingMode`. |
| Hook grabación | `useDashcamRecorder.ts` | Un Blob de `MediaRecorder` no se puede recortar en cliente → **segmentos rotativos** (rota cada 4 s, mínimo 2 s al cortar): clips siempre de 2–4 s, dentro del rango 1–6 s del backend. Posee el stream, `facingMode` y `canToggleCamera`; `switchCamera` libera pistas y pide el `facingMode` opuesto. |
| Componente | `DashcamCapture.tsx` | Loop `requestAnimationFrame` + `detectForVideo`; 6 frames alineados arman la grabación, 12 frames sin rostro la desarman; parpadeo → `stopAndCollect` → `onCapture(blob)` y cámara apagada. El CTA **Alternar Cámara** solo se renderiza si `canToggleCamera`. |

**Integración:** `LoginPage` y `RegisterPage` usan `DashcamCapture` (las mutaciones `useLogin`/`useRegister` y el contrato HTTP no cambiaron). Ante rechazo del backend, la página muestra la alerta con el motivo y el componente se re-monta reiniciando la detección sin recargar; el formulario de registro conserva sus datos (email duplicado sigue regresando al formulario). `CameraCapture` (captura manual) se conserva como fallback y **no** incluye el toggle (el flujo activo es la dashcam).

**Seguridad:** sin cambios en el modelo Zero-Trust — MediaPipe en el cliente solo decide *cuándo* cortar; el backend sigue validando liveness activo/pasivo y matching.

**Límites conocidos / pendiente manual:**
- Si el parpadeo coincide con la rotación de segmento, el clip puede no contener el ciclo completo → el backend lo rechaza por liveness y el flujo se reinicia solo (costo: un reintento).
- Falta calibración con cámara real (umbrales de EAR/alineación con distintos rostros e iluminación) y verificación en Safari/iOS (códecs de `MediaRecorder`, y el toggle frontal/trasera). Los umbrales son opciones configurables, sin refactor.

---

## Alternar cámara (frontal / trasera) — conclusiones (2026-08-22)

El CTA **no** forma parte del trigger de captura (el parpadeo sigue siendo el único disparo). Es un control de hardware opcional: si el dispositivo no tiene dos cámaras físicas, el botón **no se monta**.

### Decisión de capas (mismo patrón que Fase 7)

| Responsabilidad | Dónde | Por qué |
|---|---|---|
| Contar `videoinput` y pedir stream con `facingMode` | `videoRecorder.ts` | Funciones puras, testeables sin React; `CameraCapture` reutiliza `requestCameraStream("user")` sin cambios. |
| Estado `facingMode` / `canToggleCamera` y `switchCamera` | `useDashcamRecorder.ts` | El hook **posee** el `MediaStream` (el mismo objeto que `<video>.srcObject`). Si el componente parara pistas por su cuenta sin actualizar el hook, `MediaRecorder` seguiría ligado al stream muerto. |
| Renderizado condicional del botón | `DashcamCapture.tsx` | Al clic: detiene las pistas de video del `srcObject` del `<video>`, delega en `switchCamera` y el `useEffect` existente reasigna el stream nuevo al mismo elemento. |

### Detección de hardware

`countVideoInputDevices()` llama a `navigator.mediaDevices.enumerateDevices()` y cuenta `kind === "videoinput"`. `canToggleCamera` es `true` **solo** si el recuento es ≥ 2.

Hay que consultar **dos veces**:

1. **Al montar el hook** — cumple el requisito de detectar al entrar en la vista.
2. **Tras un `getUserMedia` exitoso** — Chrome/Safari suelen devolver 0–1 entradas (a menudo con `deviceId` vacío) *antes* del permiso. Sin la reconsulta, el botón nunca aparecería en móviles reales.

Si `enumerateDevices` no existe o lanza, el recuento es 0 → botón oculto. No se escucha `devicechange` (hotplug): un remount (reintento / rechazo del backend) vuelve a contar.

### Lógica de alternancia

- `facingMode` arranca en `"user"` (frontal). `requestCameraStream` usa `{ facingMode: { ideal } }` (no `exact`): no falla en escritorio sin cámara “trasera” etiquetada.
- Al clic, con la cámara ya activa:
  1. Se recuperan las pistas de video del `srcObject` del `<video>` y se ejecuta `.stop()` (libera el hardware; en un dispositivo típico no se pueden abrir frontal y trasera a la vez).
  2. El hook descarta la grabación en curso (`teardownSegment`), anula el stream y pide `getUserMedia` con el `facingMode` opuesto (`"environment"` ↔ `"user"`).
  3. El stream nuevo se asigna al **mismo** `<video>` (no se recrea el elemento). El loop de detección depende de `recorder.stream`: al cambiar la identidad del stream, se reinicia en fase `detecting`.
- El preview frontal sigue con `scale-x-[-1]` (selfie); el trasero no se espeja.
- El botón no se renderiza en fase `capturing` (evitar cortar el clip en el `stopAndCollect`). Durante el cambio, `stream === null` muestra “Encendiendo la cámara…”.
- Si el `facingMode` nuevo falla, el hook deja `error` y el CTA **Reintentar** vuelve a `startCamera` con el `facingMode` que sí funcionó (no se flippea el estado hasta el éxito).

### Tests útiles

- `videoRecorder.test.ts`: `countVideoInputDevices` ignora `audioinput`/`audiooutput`; `oppositeFacingMode`.
- `DashcamCapture.test.tsx`: el botón **no** aparece con 1 `videoinput`; sí con 2; el clic hace `.stop()` en las pistas y el segundo `getUserMedia` usa `{ facingMode: { ideal: "environment" } }`.

### Límites del toggle (verificar en dispositivo real)

- **`facingMode` no es `deviceId`.** En un portátil con webcam integrada + USB, ambos suelen ser `"user"`: el recuento ≥ 2 muestra el botón, pero `ideal: "environment"` puede devolver la misma cámara. En móvil (frontal/trasera) es el caso que importa y donde `facingMode` sí cambia de sensor.
- Hay que **parar las pistas viejas antes** del segundo `getUserMedia`; si no, iOS/Android a menudo ignoran el cambio o lanzan `NotReadableError`.
- Safari/iOS: confirmar que `enumerateDevices` post-permiso reporta 2 `videoinput` y que el LED/sensor cambia de verdad al pulsar el CTA.
