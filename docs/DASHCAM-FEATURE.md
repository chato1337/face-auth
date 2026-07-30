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

**Implementado y verificado** (tests: 23 en verde; `tsc`, `oxlint` y build de producción sin errores). Detalle por fase en [`MASTER_PLAN.md` §Fase 7](MASTER_PLAN.md).

**Qué se construyó** (todo en `frontend/src/components/camera/`):

| Pieza | Archivo | Decisión clave |
|---|---|---|
| Hook MediaPipe | `useFaceLandmarker.ts` | Singleton de sesión (no re-inicializa en cada reintento), fallback GPU→CPU, import dinámico (chunk lazy ~153 kB), assets por CDN pinneado a `@mediapipe/tasks-vision@1.0.0`. |
| Lógica EAR/parpadeo/alineación | `faceMetrics.ts` | EAR clásico con corrección de aspect ratio; máquina de estados con histéresis (0.20/0.25) y mínimo 2 frames cerrados; dispara al **reabrir** los ojos para que el clip contenga el ciclo completo. Alineación por bounding box con hints (`céntrate`/`acércate`/`aléjate`). |
| Hook grabación | `useDashcamRecorder.ts` | Un Blob de `MediaRecorder` no se puede recortar en cliente → **segmentos rotativos** (rota cada 4 s, mínimo 2 s al cortar): clips siempre de 2–4 s, dentro del rango 1–6 s del backend. |
| Componente | `DashcamCapture.tsx` | Loop `requestAnimationFrame` + `detectForVideo`; 6 frames alineados arman la grabación, 12 frames sin rostro la desarman; parpadeo → `stopAndCollect` → `onCapture(blob)` y cámara apagada. |

**Integración:** `LoginPage` y `RegisterPage` usan `DashcamCapture` (las mutaciones `useLogin`/`useRegister` y el contrato HTTP no cambiaron). Ante rechazo del backend, la página muestra la alerta con el motivo y el componente se re-monta reiniciando la detección sin recargar; el formulario de registro conserva sus datos (email duplicado sigue regresando al formulario). `CameraCapture` (captura manual) se conserva como fallback.

**Seguridad:** sin cambios en el modelo Zero-Trust — MediaPipe en el cliente solo decide *cuándo* cortar; el backend sigue validando liveness activo/pasivo y matching.

**Límites conocidos / pendiente manual:**
- Si el parpadeo coincide con la rotación de segmento, el clip puede no contener el ciclo completo → el backend lo rechaza por liveness y el flujo se reinicia solo (costo: un reintento).
- Falta calibración con cámara real (umbrales de EAR/alineación con distintos rostros e iluminación) y verificación en Safari/iOS (códecs de `MediaRecorder`). Los umbrales son opciones configurables, sin refactor.