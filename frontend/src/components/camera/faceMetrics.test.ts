import { describe, expect, it } from "vitest"
import type { NormalizedLandmark } from "@mediapipe/tasks-vision"

import {
  averageEyeAspectRatio,
  createBlinkDetector,
  evaluateFaceAlignment,
} from "./faceMetrics"

const FACE_LANDMARKS_COUNT = 478

/**
 * Construye una malla sintética donde ambos ojos tienen apertura vertical
 * `2 * halfOpening` y ancho horizontal 0.3, de modo que:
 * EAR = (2v + 2v) / (2 * 0.3) = halfOpening / 0.15
 */
function buildLandmarks(halfOpening: number): NormalizedLandmark[] {
  const landmarks: NormalizedLandmark[] = Array.from(
    { length: FACE_LANDMARKS_COUNT },
    () => ({ x: 0, y: 0, z: 0, visibility: 1 }),
  )

  const set = (index: number, x: number, y: number) => {
    landmarks[index] = { x, y, z: 0, visibility: 1 }
  }

  // Ojo izquierdo (en la imagen): esquinas 33-133, pares (160,144) y (158,153).
  set(33, 0.2, 0.5)
  set(133, 0.5, 0.5)
  set(160, 0.3, 0.5 - halfOpening)
  set(144, 0.3, 0.5 + halfOpening)
  set(158, 0.4, 0.5 - halfOpening)
  set(153, 0.4, 0.5 + halfOpening)

  // Ojo derecho: esquinas 362-263, pares (385,380) y (387,373).
  set(362, 0.6, 0.5)
  set(263, 0.9, 0.5)
  set(385, 0.7, 0.5 - halfOpening)
  set(380, 0.7, 0.5 + halfOpening)
  set(387, 0.8, 0.5 - halfOpening)
  set(373, 0.8, 0.5 + halfOpening)

  return landmarks
}

describe("averageEyeAspectRatio", () => {
  it("devuelve un EAR alto con los ojos abiertos", () => {
    const landmarks = buildLandmarks(0.045)
    expect(averageEyeAspectRatio(landmarks)).toBeCloseTo(0.3, 5)
  })

  it("devuelve un EAR bajo con los ojos cerrados", () => {
    const landmarks = buildLandmarks(0.0075)
    expect(averageEyeAspectRatio(landmarks)).toBeCloseTo(0.05, 5)
  })

  it("corrige la escala horizontal con el aspect ratio del video", () => {
    const landmarks = buildLandmarks(0.045)
    // Con ar=2 la distancia horizontal se duplica y el EAR cae a la mitad.
    expect(averageEyeAspectRatio(landmarks, 2)).toBeCloseTo(0.15, 5)
  })
})

describe("evaluateFaceAlignment", () => {
  /** Malla mínima cuya bounding box es el rectángulo indicado. */
  function faceBox(
    centerX: number,
    centerY: number,
    width: number,
    height: number,
  ): NormalizedLandmark[] {
    const point = (x: number, y: number): NormalizedLandmark => ({
      x,
      y,
      z: 0,
      visibility: 1,
    })
    return [
      point(centerX - width / 2, centerY),
      point(centerX + width / 2, centerY),
      point(centerX, centerY - height / 2),
      point(centerX, centerY + height / 2),
    ]
  }

  it("acepta un rostro centrado y a buena distancia", () => {
    expect(evaluateFaceAlignment(faceBox(0.5, 0.5, 0.5, 0.6))).toBe("aligned")
  })

  it("rechaza un rostro descentrado", () => {
    expect(evaluateFaceAlignment(faceBox(0.15, 0.5, 0.5, 0.6))).toBe("off_center")
  })

  it("rechaza un rostro demasiado lejos (bbox pequeña)", () => {
    expect(evaluateFaceAlignment(faceBox(0.5, 0.5, 0.1, 0.12))).toBe("too_far")
  })

  it("rechaza un rostro demasiado cerca (bbox enorme)", () => {
    expect(evaluateFaceAlignment(faceBox(0.5, 0.5, 0.95, 0.9))).toBe("too_close")
  })
})

describe("createBlinkDetector", () => {
  it("detecta un parpadeo completo (abierto → cerrado → abierto)", () => {
    const detector = createBlinkDetector({ minClosedFrames: 2 })
    const sequence = [0.3, 0.3, 0.15, 0.14, 0.3]
    const results = sequence.map((ear) => detector.update(ear))
    expect(results).toEqual([false, false, false, false, true])
  })

  it("ignora caídas de un solo frame (jitter)", () => {
    const detector = createBlinkDetector({ minClosedFrames: 2 })
    const results = [0.3, 0.15, 0.3].map((ear) => detector.update(ear))
    expect(results).toEqual([false, false, false])
  })

  it("no dispara si nunca vio los ojos abiertos antes del cierre", () => {
    const detector = createBlinkDetector({ minClosedFrames: 2 })
    const results = [0.15, 0.14, 0.3].map((ear) => detector.update(ear))
    expect(results).toEqual([false, false, false])
  })

  it("mantiene el estado en la zona intermedia de histéresis", () => {
    const detector = createBlinkDetector({
      closeThreshold: 0.2,
      openThreshold: 0.25,
      minClosedFrames: 2,
    })
    // 0.22 está entre umbrales: no cuenta como cerrado ni reabre.
    const results = [0.3, 0.15, 0.15, 0.22, 0.3].map((ear) => detector.update(ear))
    expect(results).toEqual([false, false, false, false, true])
  })

  it("reset() exige ver ojos abiertos de nuevo", () => {
    const detector = createBlinkDetector({ minClosedFrames: 1 })
    detector.update(0.3)
    detector.reset()
    const results = [0.15, 0.3].map((ear) => detector.update(ear))
    expect(results).toEqual([false, false])
  })
})
