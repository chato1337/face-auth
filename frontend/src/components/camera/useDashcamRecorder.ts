/**
 * Grabación pasiva estilo "dashcam": la cámara queda encendida, la grabación
 * arranca cuando el flujo lo indica (rostro alineado) y se detiene cuando el
 * trigger (parpadeo) lo pide, devolviendo el Blob del clip.
 *
 * Estrategia de duración — el backend acepta clips de 1–6 s, pero el usuario
 * puede tardar en parpadear. Como un Blob de MediaRecorder no se puede
 * recortar en el cliente de forma fiable, se graba en segmentos rotativos:
 * cada `maxSegmentMs` se descarta el segmento anterior y se arranca uno
 * nuevo, de modo que el segmento vigente siempre contiene los últimos ≤4 s.
 * Al detenerse, si el segmento vigente aún no alcanza `minSegmentMs`, se
 * espera lo que falte antes de cortar. Resultado: clips de 2–4 s que
 * incluyen el parpadeo.
 */

import { useCallback, useEffect, useRef, useState } from "react"

import {
  CameraError,
  pickMimeType,
  requestCameraStream,
  stopStream,
} from "@/components/camera/videoRecorder"

export const DASHCAM_RECORDING = {
  /** Duración mínima del clip entregado (margen sobre el mínimo de 1 s del backend). */
  minSegmentMs: 2000,
  /** Rotación de segmentos: cota superior del clip (< 6 s máx. del backend). */
  maxSegmentMs: 4000,
  /** Frecuencia de volcado de chunks del MediaRecorder. */
  timesliceMs: 100,
  videoBitsPerSecond: 2_500_000,
} as const

export type DashcamRecorderStatus =
  | "idle"
  | "starting_camera"
  | "camera_ready"
  | "recording"
  | "error"

export type UseDashcamRecorderResult = {
  /** Stream activo para asignar a `<video>.srcObject`; `null` si la cámara está apagada. */
  stream: MediaStream | null
  status: DashcamRecorderStatus
  error: CameraError | null
  /** Pide permiso y enciende la cámara. */
  startCamera: () => Promise<void>
  /** Apaga la cámara (descarta cualquier grabación en curso). */
  stopCamera: () => void
  /** Arranca la grabación en espera (rostro alineado). Requiere cámara encendida. */
  startRecording: () => void
  /**
   * Detiene la grabación tras el trigger (parpadeo) y resuelve con el clip.
   * Si el segmento vigente aún no dura `minSegmentMs`, espera lo que falte.
   * La cámara sigue encendida (status vuelve a `camera_ready`).
   */
  stopAndCollect: () => Promise<Blob>
  /** Descarta la grabación en curso sin producir Blob (p. ej. rostro salió del encuadre). */
  discardRecording: () => void
}

type Segment = {
  recorder: MediaRecorder
  chunks: BlobPart[]
  startedAt: number
}

export function useDashcamRecorder(
  options: Partial<typeof DASHCAM_RECORDING> = {},
): UseDashcamRecorderResult {
  const config = { ...DASHCAM_RECORDING, ...options }
  const configRef = useRef(config)
  configRef.current = config

  const streamRef = useRef<MediaStream | null>(null)
  const segmentRef = useRef<Segment | null>(null)
  const rotationTimerRef = useRef<number | null>(null)
  const collectingRef = useRef(false)
  /**
   * Turno de la sesión de cámara. `getUserMedia` es asíncrono: si mientras
   * espera el permiso hubo otro `startCamera`, un `stopCamera` o un
   * desmontaje (StrictMode monta dos veces en dev), el stream que llegue
   * tarde debe detenerse en vez de quedar huérfano con la cámara encendida.
   */
  const cameraSessionRef = useRef(0)

  const [stream, setStream] = useState<MediaStream | null>(null)
  const [status, setStatus] = useState<DashcamRecorderStatus>("idle")
  const [error, setError] = useState<CameraError | null>(null)

  const clearRotationTimer = useCallback(() => {
    if (rotationTimerRef.current !== null) {
      window.clearTimeout(rotationTimerRef.current)
      rotationTimerRef.current = null
    }
  }, [])

  /** Detiene el recorder vigente descartando sus datos, sin tocar la cámara. */
  const teardownSegment = useCallback(() => {
    clearRotationTimer()
    const segment = segmentRef.current
    segmentRef.current = null
    if (segment && segment.recorder.state !== "inactive") {
      segment.recorder.onstop = null
      segment.recorder.ondataavailable = null
      segment.recorder.stop()
    }
  }, [clearRotationTimer])

  const startSegment = useCallback(() => {
    const mediaStream = streamRef.current
    if (!mediaStream) return

    const mimeType = pickMimeType()
    const recorder = mimeType
      ? new MediaRecorder(mediaStream, {
          mimeType,
          videoBitsPerSecond: configRef.current.videoBitsPerSecond,
        })
      : new MediaRecorder(mediaStream)

    const segment: Segment = { recorder, chunks: [], startedAt: performance.now() }
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) segment.chunks.push(event.data)
    }

    segmentRef.current = segment
    recorder.start(configRef.current.timesliceMs)

    // Rotación: descartar este segmento y abrir uno nuevo, para que el clip
    // final siempre corresponda a los últimos segundos.
    rotationTimerRef.current = window.setTimeout(() => {
      if (collectingRef.current || segmentRef.current !== segment) return
      teardownSegment()
      startSegment()
    }, configRef.current.maxSegmentMs)
  }, [teardownSegment])

  const startCamera = useCallback(async () => {
    if (streamRef.current) return
    const session = ++cameraSessionRef.current
    setError(null)
    setStatus("starting_camera")
    try {
      const mediaStream = await requestCameraStream()
      if (session !== cameraSessionRef.current || streamRef.current) {
        // Llegó tarde: liberar este stream para no dejar el LED encendido.
        stopStream(mediaStream)
        return
      }
      streamRef.current = mediaStream
      setStream(mediaStream)
      setStatus("camera_ready")
    } catch (err) {
      if (session !== cameraSessionRef.current) return
      const cameraError =
        err instanceof CameraError
          ? err
          : new CameraError("unknown", "No se pudo iniciar la cámara.")
      setError(cameraError)
      setStatus("error")
      throw cameraError
    }
  }, [])

  const discardRecording = useCallback(() => {
    if (!segmentRef.current) return
    collectingRef.current = false
    teardownSegment()
    setStatus(streamRef.current ? "camera_ready" : "idle")
  }, [teardownSegment])

  const stopCamera = useCallback(() => {
    cameraSessionRef.current += 1
    collectingRef.current = false
    teardownSegment()
    stopStream(streamRef.current)
    streamRef.current = null
    setStream(null)
    setStatus("idle")
  }, [teardownSegment])

  const startRecording = useCallback(() => {
    if (!streamRef.current || segmentRef.current) return
    if (typeof MediaRecorder === "undefined") {
      const err = new CameraError(
        "unsupported",
        "MediaRecorder no está disponible en este navegador.",
      )
      setError(err)
      setStatus("error")
      return
    }
    setError(null)
    startSegment()
    setStatus("recording")
  }, [startSegment])

  const stopAndCollect = useCallback((): Promise<Blob> => {
    const segment = segmentRef.current
    if (!segment || collectingRef.current) {
      return Promise.reject(
        new CameraError("unknown", "No hay una grabación en curso."),
      )
    }

    collectingRef.current = true
    clearRotationTimer()

    const elapsed = performance.now() - segment.startedAt
    const waitMs = Math.max(0, configRef.current.minSegmentMs - elapsed)

    return new Promise<Blob>((resolve, reject) => {
      const finalize = () => {
        // El flujo pudo haberse reseteado (discard/stopCamera) durante la espera.
        if (segmentRef.current !== segment) {
          collectingRef.current = false
          reject(new CameraError("unknown", "La grabación fue descartada."))
          return
        }

        segment.recorder.onstop = () => {
          segmentRef.current = null
          collectingRef.current = false

          const type = segment.recorder.mimeType || "video/webm"
          const blob = new Blob(segment.chunks, { type })
          setStatus(streamRef.current ? "camera_ready" : "idle")

          if (blob.size === 0) {
            reject(
              new CameraError("unknown", "La grabación quedó vacía. Inténtalo de nuevo."),
            )
            return
          }
          resolve(blob)
        }
        segment.recorder.onerror = () => {
          segmentRef.current = null
          collectingRef.current = false
          setStatus(streamRef.current ? "camera_ready" : "idle")
          reject(new CameraError("unknown", "Error al grabar el video."))
        }

        if (segment.recorder.state !== "inactive") {
          segment.recorder.stop()
        }
      }

      if (waitMs > 0) {
        window.setTimeout(finalize, waitMs)
      } else {
        finalize()
      }
    })
  }, [clearRotationTimer])

  useEffect(() => {
    return () => {
      // Cleanup directo (sin depender de callbacks memoizados) al desmontar.
      cameraSessionRef.current += 1
      if (rotationTimerRef.current !== null) {
        window.clearTimeout(rotationTimerRef.current)
      }
      const segment = segmentRef.current
      if (segment && segment.recorder.state !== "inactive") {
        segment.recorder.onstop = null
        segment.recorder.ondataavailable = null
        segment.recorder.stop()
      }
      stopStream(streamRef.current)
    }
  }, [])

  return {
    stream,
    status,
    error,
    startCamera,
    stopCamera,
    startRecording,
    stopAndCollect,
    discardRecording,
  }
}
