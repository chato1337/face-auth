/** Estándar seguro de captura para el pipeline biométrico (ARCHITECTURE / MASTER_PLAN). */

export const RECORDING = {
  /** Duración del clip en milisegundos (2.5 s ≈ centro del rango 1–6 s del backend). */
  durationMs: 2500,
  /** Cuenta regresiva antes de grabar. */
  countdownSeconds: 3,
  minWidth: 640,
  minHeight: 480,
  preferredMimeTypes: [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "video/mp4",
  ] as const,
} as const

export type CameraFacingMode = "user" | "environment"

export type CameraPermissionErrorCode =
  | "denied"
  | "not_found"
  | "in_use"
  | "unsupported"
  | "unknown"

export class CameraError extends Error {
  readonly code: CameraPermissionErrorCode

  constructor(code: CameraPermissionErrorCode, message: string) {
    super(message)
    this.name = "CameraError"
    this.code = code
  }
}

export function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined
  for (const type of RECORDING.preferredMimeTypes) {
    if (MediaRecorder.isTypeSupported(type)) return type
  }
  return undefined
}

export function oppositeFacingMode(facingMode: CameraFacingMode): CameraFacingMode {
  return facingMode === "user" ? "environment" : "user"
}

/**
 * Cuenta cámaras físicas (`videoinput`). Antes del permiso de `getUserMedia`
 * algunos navegadores ocultan o colapsan la lista; conviene reconsultar
 * después de encender la cámara.
 */
export async function countVideoInputDevices(): Promise<number> {
  if (!navigator.mediaDevices?.enumerateDevices) return 0
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    return devices.filter((device) => device.kind === "videoinput").length
  } catch {
    return 0
  }
}

export async function requestCameraStream(
  facingMode: CameraFacingMode = "user",
): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new CameraError(
      "unsupported",
      "Este navegador no soporta acceso a la cámara.",
    )
  }

  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: facingMode },
        width: { ideal: RECORDING.minWidth },
        height: { ideal: RECORDING.minHeight },
      },
    })
  } catch (err) {
    const name = err instanceof DOMException ? err.name : ""
    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      throw new CameraError(
        "denied",
        "Permiso de cámara denegado. Actívalo en la configuración del navegador.",
      )
    }
    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      throw new CameraError("not_found", "No se encontró ninguna cámara disponible.")
    }
    if (name === "NotReadableError" || name === "TrackStartError") {
      throw new CameraError(
        "in_use",
        "La cámara está en uso por otra aplicación. Ciérrala e inténtalo de nuevo.",
      )
    }
    throw new CameraError(
      "unknown",
      err instanceof Error ? err.message : "No se pudo acceder a la cámara.",
    )
  }
}

export function stopStream(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((track) => track.stop())
}

export function recordClip(
  stream: MediaStream,
  durationMs: number = RECORDING.durationMs,
): Promise<Blob> {
  const mimeType = pickMimeType()
  if (!mimeType && typeof MediaRecorder === "undefined") {
    return Promise.reject(
      new CameraError("unsupported", "MediaRecorder no está disponible en este navegador."),
    )
  }

  const recorder = mimeType
    ? new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 2_500_000 })
    : new MediaRecorder(stream)

  const chunks: BlobPart[] = []

  return new Promise((resolve, reject) => {
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    recorder.onerror = () => {
      reject(new CameraError("unknown", "Error al grabar el video."))
    }
    recorder.onstop = () => {
      const type = recorder.mimeType || mimeType || "video/webm"
      const blob = new Blob(chunks, { type })
      if (blob.size === 0) {
        reject(new CameraError("unknown", "La grabación quedó vacía. Inténtalo de nuevo."))
        return
      }
      resolve(blob)
    }

    try {
      recorder.start(100)
    } catch (err) {
      reject(
        err instanceof Error
          ? err
          : new CameraError("unknown", "No se pudo iniciar la grabación."),
      )
      return
    }

    window.setTimeout(() => {
      if (recorder.state !== "inactive") {
        recorder.stop()
      }
    }, durationMs)
  })
}
