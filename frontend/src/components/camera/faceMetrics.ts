/**
 * Métricas faciales calculadas sobre los landmarks de MediaPipe Face Landmarker
 * (malla de 478 puntos). Se usan SOLO como trigger de UX en el cliente
 * (patrón "dashcam"): la validación biométrica real (liveness/anti-spoofing)
 * la hace el backend sobre el video recibido.
 */

import type { NormalizedLandmark } from "@mediapipe/tasks-vision"

/**
 * Índices de la malla para los 6 puntos del esquema EAR clásico
 * (Soukupová & Čech, 2016): p1/p4 = esquinas horizontales del ojo,
 * (p2,p6) y (p3,p5) = pares verticales párpado superior/inferior.
 *
 * "left"/"right" se refieren al lado de la imagen (la cámara frontal se
 * muestra en espejo); para el EAR promedio la lateralidad es irrelevante.
 */
const LEFT_EYE = {
  corners: [33, 133],
  verticalPairs: [
    [160, 144],
    [158, 153],
  ],
} as const

const RIGHT_EYE = {
  corners: [362, 263],
  verticalPairs: [
    [385, 380],
    [387, 373],
  ],
} as const

type EyeIndices = typeof LEFT_EYE | typeof RIGHT_EYE

/**
 * Los landmarks vienen normalizados (x relativo al ancho, y al alto), por lo
 * que un video no cuadrado distorsiona las distancias. Pasar
 * `aspectRatio = videoWidth / videoHeight` corrige la escala horizontal y
 * hace que los umbrales de EAR sean portables entre resoluciones.
 */
function distance(
  a: NormalizedLandmark,
  b: NormalizedLandmark,
  aspectRatio: number,
): number {
  return Math.hypot((a.x - b.x) * aspectRatio, a.y - b.y)
}

function eyeAspectRatio(
  landmarks: readonly NormalizedLandmark[],
  eye: EyeIndices,
  aspectRatio: number,
): number {
  const [outer, inner] = eye.corners
  const horizontal = distance(landmarks[outer], landmarks[inner], aspectRatio)
  if (horizontal === 0) return 0

  const vertical = eye.verticalPairs.reduce(
    (sum, [top, bottom]) => sum + distance(landmarks[top], landmarks[bottom], aspectRatio),
    0,
  )
  return vertical / (2 * horizontal)
}

/**
 * EAR promedio de ambos ojos. Valores de referencia: ojo abierto ≈ 0.25–0.35,
 * ojo cerrado ≈ < 0.15. Un parpadeo es una caída y recuperación rápida.
 *
 * @param landmarks los 478 puntos de `FaceLandmarkerResult.faceLandmarks[0]`.
 * @param aspectRatio `videoWidth / videoHeight` del frame analizado.
 */
export function averageEyeAspectRatio(
  landmarks: readonly NormalizedLandmark[],
  aspectRatio = 1,
): number {
  return (
    (eyeAspectRatio(landmarks, LEFT_EYE, aspectRatio) +
      eyeAspectRatio(landmarks, RIGHT_EYE, aspectRatio)) /
    2
  )
}

export type FaceAlignmentStatus = "aligned" | "off_center" | "too_far" | "too_close"

export type FaceAlignmentOptions = {
  /** Rango permitido del centro del rostro, como fracción del frame. */
  centerXRange?: readonly [number, number]
  centerYRange?: readonly [number, number]
  /** Ancho del rostro (bbox) como fracción del ancho del frame. */
  minFaceWidth?: number
  maxFaceWidth?: number
}

/**
 * Evalúa si el rostro está razonablemente centrado y a buena distancia,
 * usando la bounding box de los landmarks en coordenadas normalizadas.
 * Los rangos son deliberadamente tolerantes: el encuadre fino lo valida el
 * backend (`FramePreprocessor`); aquí solo se decide cuándo armar el trigger.
 */
export function evaluateFaceAlignment(
  landmarks: readonly NormalizedLandmark[],
  options: FaceAlignmentOptions = {},
): FaceAlignmentStatus {
  const {
    centerXRange = [0.3, 0.7],
    centerYRange = [0.28, 0.72],
    minFaceWidth = 0.28,
    maxFaceWidth = 0.85,
  } = options

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const point of landmarks) {
    if (point.x < minX) minX = point.x
    if (point.x > maxX) maxX = point.x
    if (point.y < minY) minY = point.y
    if (point.y > maxY) maxY = point.y
  }

  const width = maxX - minX
  if (width < minFaceWidth) return "too_far"
  if (width > maxFaceWidth) return "too_close"

  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2
  if (
    centerX < centerXRange[0] ||
    centerX > centerXRange[1] ||
    centerY < centerYRange[0] ||
    centerY > centerYRange[1]
  ) {
    return "off_center"
  }

  return "aligned"
}

export type BlinkDetectorOptions = {
  /** EAR por debajo del cual el ojo se considera cerrado. */
  closeThreshold?: number
  /** EAR por encima del cual el ojo se considera abierto (histéresis anti-ruido). */
  openThreshold?: number
  /** Frames consecutivos "cerrado" necesarios para validar el parpadeo. */
  minClosedFrames?: number
}

export type BlinkDetector = {
  /**
   * Alimentar con el EAR de cada frame procesado. Devuelve `true` una sola
   * vez, en el frame en que el parpadeo se completa (ojos reabiertos), para
   * que el clip grabado contenga el ciclo cerrar-abrir completo.
   */
  update: (ear: number) => boolean
  /** Reinicia el estado interno (p. ej. si el rostro sale del encuadre). */
  reset: () => void
}

/**
 * Máquina de estados abierto → cerrado → abierto con histéresis:
 * - Exige ver los ojos abiertos antes de aceptar un cierre (evita disparar
 *   si la detección arranca con los ojos ya cerrados).
 * - `minClosedFrames` filtra caídas de un solo frame por jitter de landmarks.
 */
export function createBlinkDetector(options: BlinkDetectorOptions = {}): BlinkDetector {
  const {
    closeThreshold = 0.2,
    openThreshold = 0.25,
    minClosedFrames = 2,
  } = options

  let openSeen = false
  let closedFrames = 0

  return {
    update(ear: number): boolean {
      if (!openSeen) {
        if (ear >= openThreshold) openSeen = true
        return false
      }

      if (ear <= closeThreshold) {
        closedFrames += 1
        return false
      }

      if (ear >= openThreshold) {
        const blinked = closedFrames >= minClosedFrames
        closedFrames = 0
        return blinked
      }

      // Zona intermedia (entre umbrales): mantener el estado actual.
      return false
    },

    reset() {
      openSeen = false
      closedFrames = 0
    },
  }
}
