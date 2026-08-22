import { StrictMode } from "react"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi, type Mock } from "vitest"
import type { NormalizedLandmark } from "@mediapipe/tasks-vision"

import { DashcamCapture } from "@/components/camera/DashcamCapture"

// Evita descargar WASM/modelo en jsdom; cada test controla el valor devuelto.
vi.mock("@/components/camera/useFaceLandmarker", () => ({
  useFaceLandmarker: vi.fn(),
}))

import { useFaceLandmarker } from "@/components/camera/useFaceLandmarker"

const mockUseFaceLandmarker = useFaceLandmarker as Mock

function landmarkerHookValue(overrides: Partial<ReturnType<typeof useFaceLandmarker>> = {}) {
  return {
    landmarker: null,
    status: "loading" as const,
    error: null,
    retry: vi.fn(),
    ...overrides,
  }
}

/**
 * Malla sintética centrada (bbox ~0.36 de ancho) con ojos parametrizables:
 * suficiente para que `evaluateFaceAlignment` acepte y el EAR sea controlable.
 */
function buildFace(halfOpening: number): NormalizedLandmark[] {
  const landmarks: NormalizedLandmark[] = Array.from({ length: 478 }, () => ({
    x: 0.5,
    y: 0.5,
    z: 0,
    visibility: 1,
  }))
  const set = (index: number, x: number, y: number) => {
    landmarks[index] = { x, y, z: 0, visibility: 1 }
  }

  // Contorno para la bounding box (centrado, tamaño válido).
  set(10, 0.5, 0.3) // frente
  set(152, 0.5, 0.7) // mentón
  set(234, 0.32, 0.5) // lateral izq
  set(454, 0.68, 0.5) // lateral der

  // Ojo izquierdo (EAR = halfOpening * 2 / 0.1 con ancho de ojo 0.1).
  set(33, 0.38, 0.45)
  set(133, 0.48, 0.45)
  set(160, 0.41, 0.45 - halfOpening)
  set(144, 0.41, 0.45 + halfOpening)
  set(158, 0.44, 0.45 - halfOpening)
  set(153, 0.44, 0.45 + halfOpening)

  // Ojo derecho.
  set(362, 0.52, 0.45)
  set(263, 0.62, 0.45)
  set(385, 0.55, 0.45 - halfOpening)
  set(380, 0.55, 0.45 + halfOpening)
  set(387, 0.58, 0.45 - halfOpening)
  set(373, 0.58, 0.45 + halfOpening)

  return landmarks
}

// EAR = 20 * halfOpening (ancho de ojo 0.1, video cuadrado en el test).
const OPEN_EYES = buildFace(0.015) // EAR 0.30
const CLOSED_EYES = buildFace(0.0025) // EAR 0.05

type FrameScript = NormalizedLandmark[][]

function fakeLandmarker(script: FrameScript) {
  let frame = 0
  return {
    detectForVideo: vi.fn(() => {
      const landmarks = script[Math.min(frame, script.length - 1)]
      frame += 1
      return { faceLandmarks: landmarks.length ? [landmarks] : [] }
    }),
  } as unknown as NonNullable<ReturnType<typeof useFaceLandmarker>["landmarker"]>
}

class FakeMediaRecorder {
  static isTypeSupported = () => true
  state: RecordingState = "inactive"
  mimeType = "video/webm"
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}

  start(_timeslice?: number) {
    this.state = "recording"
    queueMicrotask(() => {
      this.ondataavailable?.({ data: new Blob(["chunk"], { type: "video/webm" }) })
    })
  }

  stop() {
    this.state = "inactive"
    this.onstop?.()
  }
}

function videoInputs(count: number): MediaDeviceInfo[] {
  return Array.from({ length: count }, (_, index) => ({
    kind: "videoinput",
    deviceId: `cam-${index}`,
    label: `Camera ${index}`,
    groupId: "",
    toJSON() {
      return this
    },
  })) as MediaDeviceInfo[]
}

function installFakeCamera(options: { videoInputCount?: number } = {}) {
  const track = { stop: vi.fn() }
  const stream = {
    getTracks: () => [track],
    getVideoTracks: () => [track],
  } as unknown as MediaStream

  const getUserMedia = vi.fn().mockResolvedValue(stream)
  const enumerateDevices = vi
    .fn()
    .mockResolvedValue(videoInputs(options.videoInputCount ?? 1))

  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia, enumerateDevices },
  })
  HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(HTMLMediaElement.prototype, "readyState", {
    configurable: true,
    get: () => 4,
  })
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
    configurable: true,
    get: () => 480,
  })
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
    configurable: true,
    get: () => 480,
  })
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder)

  return { track, getUserMedia, stream }
}

afterEach(() => {
  vi.unstubAllGlobals()
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: undefined,
  })
})

describe("DashcamCapture", () => {
  it("muestra error y permite reintentar/cancelar si la cámara no está disponible", async () => {
    // jsdom sin mediaDevices → CameraError "unsupported".
    mockUseFaceLandmarker.mockReturnValue(
      landmarkerHookValue({ status: "ready", landmarker: fakeLandmarker([[]]) }),
    )
    const onCancel = vi.fn()
    const user = userEvent.setup()

    render(<DashcamCapture onCapture={vi.fn()} onCancel={onCancel} />)

    expect(
      await screen.findByText(/no soporta acceso a la cámara/i),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /cancelar/i }))
    expect(onCancel).toHaveBeenCalled()
  })

  it("indica que está preparando el detector mientras carga MediaPipe", async () => {
    installFakeCamera()
    mockUseFaceLandmarker.mockReturnValue(landmarkerHookValue({ status: "loading" }))

    render(<DashcamCapture onCapture={vi.fn()} />)

    expect(
      await screen.findByText(/preparando el detector facial/i),
    ).toBeInTheDocument()
  })

  it("no deja streams huérfanos con el doble montaje de StrictMode", async () => {
    // StrictMode dispara startCamera dos veces con getUserMedia pendiente:
    // el primer stream debe detenerse al llegar tarde (LED de cámara apagado).
    const tracks: Mock[] = []
    const makeStream = () => {
      const stop = vi.fn()
      tracks.push(stop)
      return {
        getTracks: () => [{ stop }],
        getVideoTracks: () => [{ stop }],
      } as unknown as MediaStream
    }
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockImplementation(() => Promise.resolve(makeStream())),
      },
    })
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    mockUseFaceLandmarker.mockReturnValue(landmarkerHookValue({ status: "loading" }))

    const { unmount } = render(
      <StrictMode>
        <DashcamCapture onCapture={vi.fn()} />
      </StrictMode>,
    )

    await waitFor(() => expect(tracks).toHaveLength(2))
    await waitFor(() => expect(tracks[0]).toHaveBeenCalled())
    expect(tracks[1]).not.toHaveBeenCalled()

    // Al desmontar, el stream adoptado también se libera.
    unmount()
    expect(tracks[1]).toHaveBeenCalled()
  })

  it("arma la grabación con el rostro alineado y captura tras el parpadeo", async () => {
    const { track } = installFakeCamera()

    // 10 frames alineado/ojos abiertos → arma; 4 cerrados + reapertura → dispara.
    const script: FrameScript = [
      ...Array.from({ length: 10 }, () => OPEN_EYES),
      ...Array.from({ length: 4 }, () => CLOSED_EYES),
      OPEN_EYES,
    ]
    mockUseFaceLandmarker.mockReturnValue(
      landmarkerHookValue({ status: "ready", landmarker: fakeLandmarker(script) }),
    )

    const onCapture = vi.fn()
    render(<DashcamCapture onCapture={onCapture} />)

    expect(
      await screen.findByText(/rostro detectado\. parpadee para confirmar/i),
    ).toBeInTheDocument()

    // stopAndCollect espera hasta completar el mínimo de 2 s del clip.
    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1), {
      timeout: 4000,
    })
    const blob = onCapture.mock.calls[0][0] as Blob
    expect(blob.size).toBeGreaterThan(0)
    // La cámara se apaga tras entregar el clip.
    expect(track.stop).toHaveBeenCalled()
  })

  it("no muestra Alternar Cámara si hay una sola videoinput", async () => {
    installFakeCamera({ videoInputCount: 1 })
    mockUseFaceLandmarker.mockReturnValue(
      landmarkerHookValue({ status: "ready", landmarker: fakeLandmarker([[]]) }),
    )

    render(<DashcamCapture onCapture={vi.fn()} />)

    expect(await screen.findByText(/buscando tu rostro/i)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /alternar cámara/i })).not.toBeInTheDocument()
  })

  it("muestra Alternar Cámara solo con 2 o más videoinput", async () => {
    installFakeCamera({ videoInputCount: 2 })
    mockUseFaceLandmarker.mockReturnValue(
      landmarkerHookValue({ status: "ready", landmarker: fakeLandmarker([[]]) }),
    )

    render(<DashcamCapture onCapture={vi.fn()} />)

    expect(
      await screen.findByRole("button", { name: /alternar cámara/i }),
    ).toBeInTheDocument()
  })

  it("al alternar libera las pistas y pide el facingMode opuesto", async () => {
    const { track, getUserMedia } = installFakeCamera({ videoInputCount: 2 })
    mockUseFaceLandmarker.mockReturnValue(
      landmarkerHookValue({ status: "ready", landmarker: fakeLandmarker([[]]) }),
    )
    const user = userEvent.setup()

    render(<DashcamCapture onCapture={vi.fn()} />)

    await user.click(await screen.findByRole("button", { name: /alternar cámara/i }))

    await waitFor(() => expect(track.stop).toHaveBeenCalled())
    await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(2))
    expect(getUserMedia).toHaveBeenLastCalledWith({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
    })
  })
})
