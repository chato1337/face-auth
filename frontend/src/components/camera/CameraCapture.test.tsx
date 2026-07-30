import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { CameraCapture } from "@/components/camera/CameraCapture"

describe("CameraCapture", () => {
  it("muestra CTA para activar cámara", () => {
    render(<CameraCapture onCapture={vi.fn()} />)
    expect(
      screen.getByRole("button", { name: /activar cámara/i }),
    ).toBeInTheDocument()
  })

  it("muestra error claro si getUserMedia no está disponible", async () => {
    const user = userEvent.setup()
    const original = navigator.mediaDevices
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    })

    render(<CameraCapture onCapture={vi.fn()} />)
    await user.click(screen.getByRole("button", { name: /activar cámara/i }))

    expect(await screen.findByText(/no soporta acceso a la cámara/i)).toBeInTheDocument()

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: original,
    })
  })
})
