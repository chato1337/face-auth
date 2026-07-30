/**
 * Inicialización eficiente de MediaPipe Face Landmarker (WASM) para el patrón
 * "dashcam". El modelo corre en el navegador únicamente como trigger de UX
 * (rostro alineado + parpadeo); el backend sigue haciendo la validación
 * biométrica real sobre el video.
 */

import { useCallback, useEffect, useState } from "react"
import type { FaceLandmarker } from "@mediapipe/tasks-vision"

/** Mantener en sync con la versión de `@mediapipe/tasks-vision` en package.json. */
const MEDIAPIPE_TASKS_VERSION = "1.0.0"

export const FACE_LANDMARKER_ASSETS = {
  /** Runtime WASM servido por CDN, fijado a la versión instalada. */
  wasmBasePath: `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_TASKS_VERSION}/wasm`,
  /** Bundle oficial del modelo (~3.7 MB, float16). */
  modelAssetPath:
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
} as const

/**
 * Singleton a nivel de módulo: cargar el WASM + modelo toma cientos de ms y
 * el flujo dashcam se reinicia varias veces sin recargar la página (p. ej.
 * cuando el backend rechaza un intento). Se crea una sola vez por sesión y
 * se comparte entre montajes; no se llama a `close()` en el unmount para no
 * pagar la re-inicialización en cada reintento.
 */
let landmarkerPromise: Promise<FaceLandmarker> | null = null

async function createLandmarker(): Promise<FaceLandmarker> {
  // Import dinámico: el bundle JS de tasks-vision pesa cientos de kB y solo
  // lo necesitan las vistas de captura (no el panel admin ni la carga inicial).
  const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision")

  const fileset = await FilesetResolver.forVisionTasks(
    FACE_LANDMARKER_ASSETS.wasmBasePath,
  )

  const commonOptions = {
    runningMode: "VIDEO" as const,
    numFaces: 1,
    // Solo necesitamos los landmarks para EAR/alineación; blendshapes y
    // matrices de transformación agregan costo por frame sin aportar nada.
    outputFaceBlendshapes: false,
    outputFacialTransformationMatrixes: false,
  }

  try {
    return await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath: FACE_LANDMARKER_ASSETS.modelAssetPath,
        delegate: "GPU",
      },
      ...commonOptions,
    })
  } catch {
    // Algunos navegadores/dispositivos no soportan el delegate GPU (WebGL);
    // CPU es más lento pero suficiente para un trigger de UX.
    return FaceLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath: FACE_LANDMARKER_ASSETS.modelAssetPath,
        delegate: "CPU",
      },
      ...commonOptions,
    })
  }
}

function loadFaceLandmarker(): Promise<FaceLandmarker> {
  if (!landmarkerPromise) {
    landmarkerPromise = createLandmarker().catch((err: unknown) => {
      // No cachear el fallo: permite reintentar (p. ej. red intermitente).
      landmarkerPromise = null
      throw err
    })
  }
  return landmarkerPromise
}

export type FaceLandmarkerStatus = "loading" | "ready" | "error"

export type UseFaceLandmarkerResult = {
  /**
   * Instancia lista para `detectForVideo(video, timestampMs)`. Es `null`
   * mientras carga o si falló. Llamarla desde un loop de
   * `requestAnimationFrame` propio del componente (una inferencia por frame
   * pintado; la llamada es síncrona y no bloquea entre frames).
   */
  landmarker: FaceLandmarker | null
  status: FaceLandmarkerStatus
  error: Error | null
  /** Reintenta la descarga/inicialización tras un error. */
  retry: () => void
}

export function useFaceLandmarker(): UseFaceLandmarkerResult {
  const [landmarker, setLandmarker] = useState<FaceLandmarker | null>(null)
  const [status, setStatus] = useState<FaceLandmarkerStatus>("loading")
  const [error, setError] = useState<Error | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setStatus("loading")
    setError(null)

    loadFaceLandmarker()
      .then((instance) => {
        if (cancelled) return
        setLandmarker(instance)
        setStatus("ready")
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(
          err instanceof Error
            ? err
            : new Error("No se pudo inicializar el detector facial."),
        )
        setStatus("error")
      })

    return () => {
      cancelled = true
    }
  }, [attempt])

  const retry = useCallback(() => {
    setAttempt((n) => n + 1)
  }, [])

  return { landmarker, status, error, retry }
}
