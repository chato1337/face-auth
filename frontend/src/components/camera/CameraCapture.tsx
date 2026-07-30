import { useEffect, useRef, useState } from "react"
import { Camera, RefreshCw } from "lucide-react"

import {
  CameraError,
  RECORDING,
  recordClip,
  requestCameraStream,
  stopStream,
} from "@/components/camera/videoRecorder"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

type Phase = "idle" | "preview" | "countdown" | "recording" | "done" | "error"

type CameraCaptureProps = {
  onCapture: (blob: Blob) => void
  onCancel?: () => void
  disabled?: boolean
  className?: string
}

export function CameraCapture({
  onCapture,
  onCancel,
  disabled = false,
  className,
}: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [phase, setPhase] = useState<Phase>("idle")
  const [countdown, setCountdown] = useState(RECORDING.countdownSeconds)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      stopStream(streamRef.current)
      streamRef.current = null
    }
  }, [])

  async function startPreview() {
    setError(null)
    setPhase("idle")
    try {
      const stream = await requestCameraStream()
      stopStream(streamRef.current)
      streamRef.current = stream
      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        await video.play()
      }
      setPhase("preview")
    } catch (err) {
      const message =
        err instanceof CameraError
          ? err.message
          : "No se pudo iniciar la cámara."
      setError(message)
      setPhase("error")
    }
  }

  async function startRecording() {
    if (!streamRef.current || disabled) return
    setError(null)
    setPhase("countdown")
    setCountdown(RECORDING.countdownSeconds)

    for (let i = RECORDING.countdownSeconds; i > 0; i -= 1) {
      setCountdown(i)
      await wait(1000)
    }

    setPhase("recording")
    try {
      const blob = await recordClip(streamRef.current)
      setPhase("done")
      stopStream(streamRef.current)
      streamRef.current = null
      if (videoRef.current) {
        videoRef.current.srcObject = null
      }
      onCapture(blob)
    } catch (err) {
      const message =
        err instanceof CameraError
          ? err.message
          : "Error al grabar. Inténtalo de nuevo."
      setError(message)
      setPhase("error")
    }
  }

  function handleRetry() {
    void startPreview()
  }

  const busy = phase === "countdown" || phase === "recording"
  const showVideo = phase === "preview" || phase === "countdown" || phase === "recording"

  return (
    <div className={cn("flex w-full flex-col gap-4", className)}>
      <div className="relative mx-auto aspect-[3/4] w-full max-w-sm overflow-hidden rounded-2xl bg-zinc-950 shadow-inner ring-1 ring-white/10">
        <video
          ref={videoRef}
          playsInline
          muted
          className={cn(
            "h-full w-full scale-x-[-1] object-cover transition-opacity duration-300",
            showVideo ? "opacity-100" : "opacity-0",
          )}
        />

        {!showVideo && phase !== "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center text-zinc-300">
            <Camera className="size-10 opacity-70" aria-hidden />
            <p className="text-sm text-zinc-400">
              Necesitamos acceso a tu cámara para el reconocimiento facial.
            </p>
          </div>
        )}

        {/* Face oval guide */}
        {showVideo && (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center"
            aria-hidden
          >
            <div
              className={cn(
                "h-[62%] w-[72%] rounded-[50%] border-2 transition-colors duration-300",
                phase === "recording"
                  ? "border-emerald-400/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]"
                  : "border-white/70 shadow-[0_0_0_9999px_rgba(0,0,0,0.4)]",
              )}
            />
          </div>
        )}

        {phase === "countdown" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/25">
            <span
              key={countdown}
              className="animate-in zoom-in-50 fade-in text-7xl font-semibold text-white duration-300"
            >
              {countdown}
            </span>
          </div>
        )}

        {phase === "recording" && (
          <div className="absolute top-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-black/55 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm">
            <span className="size-2 animate-pulse rounded-full bg-red-500" />
            Grabando…
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Cámara</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <p className="text-center text-sm text-muted-foreground">
        Centra tu rostro, parpadea con naturalidad y mantén la cabeza ligeramente en
        movimiento. Clip de ~{RECORDING.durationMs / 1000}s.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-2">
        {phase === "idle" || phase === "error" || phase === "done" ? (
          <Button
            type="button"
            size="lg"
            disabled={disabled}
            onClick={() => void startPreview()}
          >
            <Camera data-icon="inline-start" />
            {phase === "error" || phase === "done" ? "Reintentar cámara" : "Activar cámara"}
          </Button>
        ) : null}

        {phase === "preview" ? (
          <Button
            type="button"
            size="lg"
            disabled={disabled}
            onClick={() => void startRecording()}
          >
            Grabar rostro
          </Button>
        ) : null}

        {busy ? (
          <Button type="button" size="lg" disabled>
            <Spinner data-icon="inline-start" />
            {phase === "countdown" ? "Prepárate…" : "Grabando…"}
          </Button>
        ) : null}

        {phase === "error" ? (
          <Button type="button" variant="outline" size="lg" onClick={handleRetry}>
            <RefreshCw data-icon="inline-start" />
            Reintentar
          </Button>
        ) : null}

        {onCancel && !busy ? (
          <Button type="button" variant="ghost" size="lg" onClick={onCancel}>
            Cancelar
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}
