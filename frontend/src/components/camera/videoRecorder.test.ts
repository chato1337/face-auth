import { afterEach, describe, expect, it, vi } from "vitest"

import {
  RECORDING,
  countVideoInputDevices,
  oppositeFacingMode,
  pickMimeType,
} from "@/components/camera/videoRecorder"

afterEach(() => {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: undefined,
  })
})

describe("videoRecorder", () => {
  it("usa duración segura 2–3s", () => {
    expect(RECORDING.durationMs).toBeGreaterThanOrEqual(2000)
    expect(RECORDING.durationMs).toBeLessThanOrEqual(3000)
  })

  it("exige resolución mínima razonable", () => {
    expect(RECORDING.minWidth).toBeGreaterThanOrEqual(640)
    expect(RECORDING.minHeight).toBeGreaterThanOrEqual(480)
  })

  it("pickMimeType no lanza sin MediaRecorder", () => {
    expect(() => pickMimeType()).not.toThrow()
  })

  it("oppositeFacingMode alterna user ↔ environment", () => {
    expect(oppositeFacingMode("user")).toBe("environment")
    expect(oppositeFacingMode("environment")).toBe("user")
  })

  it("countVideoInputDevices devuelve 0 si la API no está disponible", async () => {
    expect(await countVideoInputDevices()).toBe(0)
  })

  it("countVideoInputDevices solo cuenta dispositivos videoinput", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        enumerateDevices: vi.fn().mockResolvedValue([
          { kind: "audioinput", deviceId: "mic" },
          { kind: "videoinput", deviceId: "cam-1" },
          { kind: "videoinput", deviceId: "cam-2" },
          { kind: "audiooutput", deviceId: "spk" },
        ]),
      },
    })

    expect(await countVideoInputDevices()).toBe(2)
  })
})
