import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { LoginPage } from "@/features/login/LoginPage"

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

function renderLogin() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("LoginPage", () => {
  it("muestra el botón de inicio biométrico", () => {
    renderLogin()
    expect(
      screen.getByRole("button", { name: /iniciar sesión con rostro/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Face-Auth/i)).toBeInTheDocument()
  })
})
