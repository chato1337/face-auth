import { describe, expect, it } from "vitest"

import { RECORDING, pickMimeType } from "@/components/camera/videoRecorder"

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
})
