import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { RegisterPage } from "@/features/register/RegisterPage"

vi.mock("@/context/TenantContext", () => ({
  useTenant: () => ({
    appId: "app_test",
    redirectUri: null,
    application: {
      app_id: "app_test",
      name: "Demo",
      is_active: true,
      redirect_uris: [],
      liveness_threshold: 0.85,
      match_threshold: 0.42,
    },
  }),
}))

// Evita que DashcamCapture descargue el WASM/modelo de MediaPipe en jsdom.
vi.mock("@/components/camera/useFaceLandmarker", () => ({
  useFaceLandmarker: () => ({
    landmarker: null,
    status: "loading",
    error: null,
    retry: vi.fn(),
  }),
}))

function renderRegister() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("RegisterPage", () => {
  it("conserva los datos del formulario al pasar a captura", async () => {
    const user = userEvent.setup()
    renderRegister()

    await user.type(screen.getByLabelText(/nombres/i), "Ada")
    await user.type(screen.getByLabelText(/apellidos/i), "Lovelace")
    await user.type(screen.getByLabelText(/correo/i), "ada@example.com")
    await user.click(screen.getByRole("button", { name: /registro biométrico/i }))

    // En jsdom no hay getUserMedia: la captura automática muestra el error
    // de cámara, pero el flujo permite cancelar y volver al formulario.
    expect(
      await screen.findByText(/no soporta acceso a la cámara/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /cancelar/i }))

    expect(screen.getByLabelText(/nombres/i)).toHaveValue("Ada")
    expect(screen.getByLabelText(/correo/i)).toHaveValue("ada@example.com")
  })
})
