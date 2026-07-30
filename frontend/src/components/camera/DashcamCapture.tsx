/**
 * Captura pasiva estilo "dashcam" (docs/dashcam-feat.md): la cámara enciende
 * al montar, un loop de requestAnimationFrame corre MediaPipe Face Landmarker
 * sobre el stream, la grabación arranca cuando el rostro queda alineado en el
 * óvalo y un parpadeo (caída y recuperación del EAR) dispara el corte y el
 * auto-envío del clip vía `onCapture`.
 *
 * MediaPipe aquí es SOLO un trigger de conveniencia (UX): la validación de
 * liveness/anti-spoofing real la hace el backend sobre el video recibido.
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw, ScanFace } from "lucide-react"

import {
  averageEyeAspectRatio,
  createBlinkDetector,
  evaluateFaceAlignment,
  type FaceAlignmentStatus,
} from "@/components/camera/faceMetrics"
import { useDashcamRecorder } from "@/components/camera/useDashcamRecorder"
import { useFaceLandmarker } from "@/components/camera/useFaceLandmarker"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

const DETECTION = {
  /** Frames consecutivos alineados para armar la grabación (estabilidad). */
  stableFrames: 6,
  /** Frames consecutivos sin rostro alineado para desarmar y volver a buscar. */
  lostFrames: 12,
} as const

type DashcamPhase = "detecting" | "waiting_blink" | "capturing"

type DashcamCaptureProps = {
  /** Recibe el clip listo para enviarse al backend. */
  onCapture: (blob: Blob) => void
  onCancel?: () => void
  /** Pausa el trigger (p. ej. mientras hay una mutación en curso). */
  disabled?: boolean
  className?: string
}

const HINT_BY_ALIGNMENT: Record<Exclude<FaceAlignmentStatus, "aligned">, string> = {
  off_center: "Centra tu rostro en el óvalo",
  too_far: "Acércate un poco a la cámara",
  too_close: "Aléjate un poco de la cámara",
}

export function DashcamCapture({
  onCapture,
  onCancel,
  disabled = false,
  className,
}: DashcamCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const phaseRef = useRef<DashcamPhase>("detecting")
  const onCaptureRef = useRef(onCapture)
  onCaptureRef.current = onCapture

  const [phase, setPhaseState] = useState<DashcamPhase>("detecting")
  const [hint, setHint] = useState<string | null>(null)

  const landmarkerState = useFaceLandmarker()
  const recorder = useDashcamRecorder()
  const { startCamera, startRecording, stopAndCollect, discardRecording, stopCamera } =
    recorder

  const setPhase = useCallback((next: DashcamPhase) => {
    phaseRef.current = next
    setPhaseState(next)
  }, [])

  // 1. Encender la cámara al montar (el hook registra el error si falla).
  useEffect(() => {
    void startCamera().catch(() => {})
  }, [startCamera])

  // 2. Conectar el stream al <video>.
  useEffect(() => {
    const video = videoRef.current
    if (!video || !recorder.stream) return
    video.srcObject = recorder.stream
    void video.play().catch(() => {})
    return () => {
      video.srcObject = null
    }
  }, [recorder.stream])

  // 3. Loop de detección: una inferencia por frame pintado (rAF). La llamada
  //    a detectForVideo es síncrona y corre fuera del ciclo de render de React;
  //    solo se toca el estado en las transiciones de fase.
  useEffect(() => {
    const landmarker = landmarkerState.landmarker
    if (!landmarker || !recorder.stream || disabled) return

    let cancelled = false
    let rafId = 0
    let lastTimestamp = -1
    let alignedFrames = 0
    let lostFrames = 0
    const blinkDetector = createBlinkDetector()

    setPhase("detecting")
    setHint(null)

    const handleBlink = () => {
      setPhase("capturing")
      stopAndCollect()
        .then((blob) => {
          stopCamera()
          onCaptureRef.current(blob)
        })
        .catch(() => {
          // Grabación descartada o error del recorder: volver a detectar.
          if (cancelled) return
          blinkDetector.reset()
          alignedFrames = 0
          setPhase("detecting")
        })
    }

    const tick = () => {
      if (cancelled) return
      rafId = requestAnimationFrame(tick)

      const video = videoRef.current
      if (!video || video.readyState < 2 || video.videoWidth === 0) return

      // detectForVideo exige timestamps estrictamente crecientes.
      const timestamp = performance.now()
      if (timestamp <= lastTimestamp) return
      lastTimestamp = timestamp

      const currentPhase = phaseRef.current
      if (currentPhase === "capturing") return

      const result = landmarker.detectForVideo(video, timestamp)
      const landmarks = result.faceLandmarks[0]
      const alignment = landmarks ? evaluateFaceAlignment(landmarks) : null

      if (alignment !== "aligned") {
        alignedFrames = 0
        lostFrames += 1
        setHint(alignment ? HINT_BY_ALIGNMENT[alignment] : null)
        if (currentPhase === "waiting_blink" && lostFrames >= DETECTION.lostFrames) {
          discardRecording()
          blinkDetector.reset()
          setPhase("detecting")
        }
        return
      }

      lostFrames = 0
      setHint(null)

      if (currentPhase === "detecting") {
        alignedFrames += 1
        if (alignedFrames >= DETECTION.stableFrames) {
          blinkDetector.reset()
          startRecording()
          setPhase("waiting_blink")
        }
        return
      }

      // waiting_blink: evaluar EAR y disparar con el parpadeo completo.
      const ear = averageEyeAspectRatio(landmarks, video.videoWidth / video.videoHeight)
      if (blinkDetector.update(ear)) {
        handleBlink()
      }
    }

    rafId = requestAnimationFrame(tick)
    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
    }
  }, [
    landmarkerState.landmarker,
    recorder.stream,
    disabled,
    setPhase,
    startRecording,
    stopAndCollect,
    discardRecording,
    stopCamera,
  ])

  function handleRetry() {
    if (landmarkerState.status === "error") landmarkerState.retry()
    void startCamera().catch(() => {})
  }

  const error = recorder.error?.message ?? landmarkerState.error?.message ?? null
  const initializing =
    !error && (landmarkerState.status === "loading" || !recorder.stream)
  const active = !error && !initializing

  const statusMessage =
    phase === "capturing"
      ? "Capturando…"
      : phase === "waiting_blink"
        ? "Rostro detectado. Parpadee para confirmar"
        : (hint ?? "Buscando tu rostro…")

  return (
    <div className={cn("flex w-full flex-col gap-4", className)}>
      <div className="relative mx-auto aspect-[3/4] w-full max-w-sm overflow-hidden rounded-2xl bg-zinc-950 shadow-inner ring-1 ring-white/10">
        <video
          ref={videoRef}
          playsInline
          muted
          className={cn(
            "h-full w-full scale-x-[-1] object-cover transition-opacity duration-300",
            active ? "opacity-100" : "opacity-0",
          )}
        />

        {initializing && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center text-zinc-300">
            <Spinner className="size-8 opacity-80" />
            <p className="text-sm text-zinc-400">
              {landmarkerState.status === "loading"
                ? "Preparando el detector facial…"
                : "Encendiendo la cámara…"}
            </p>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center text-zinc-300">
            <ScanFace className="size-10 opacity-70" aria-hidden />
            <p className="text-sm text-zinc-400">
              No se pudo iniciar la captura automática.
            </p>
          </div>
        )}

        {/* Óvalo guía: cambia de color según la fase del trigger. */}
        {active && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              aria-hidden
              className={cn(
                "h-[62%] w-[72%] rounded-[50%] border-2 bg-transparent transition-colors duration-300",
                "shadow-[0_0_0_9999px_rgba(0,0,0,0.4)]",
                phase === "detecting" && "border-white/70",
                phase === "waiting_blink" && "border-emerald-400/90",
                phase === "capturing" && "animate-pulse border-emerald-300",
              )}
            />
          </div>
        )}

        {active && (
          <div
            role="status"
            className="absolute top-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-black/55 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm"
          >
            {phase === "waiting_blink" && (
              <span className="size-2 animate-pulse rounded-full bg-emerald-400" />
            )}
            {phase === "capturing" && (
              <span className="size-2 animate-pulse rounded-full bg-red-500" />
            )}
            {statusMessage}
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Captura automática</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <p className="text-center text-sm text-muted-foreground">
        Sin botones: ubica tu rostro dentro del óvalo y{" "}
        <span className="font-medium text-foreground">parpadea</span> para confirmar.
        El video se envía automáticamente.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-2">
        {error && (
          <Button type="button" variant="outline" size="lg" onClick={handleRetry}>
            <RefreshCw data-icon="inline-start" />
            Reintentar
          </Button>
        )}
        {onCancel && phase !== "capturing" && (
          <Button type="button" variant="ghost" size="lg" onClick={onCancel}>
            Cancelar
          </Button>
        )}
      </div>
    </div>
  )
}
