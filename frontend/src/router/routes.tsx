import type { ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { TenantProvider } from "@/context/TenantContext"
import { LoginPage } from "@/features/login/LoginPage"
import { NotFoundPage } from "@/features/not-found/NotFoundPage"
import { RegisterPage } from "@/features/register/RegisterPage"

function TenantRoute({ children }: { children: ReactNode }) {
  return <TenantProvider>{children}</TenantProvider>
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route
        path="/login"
        element={
          <TenantRoute>
            <LoginPage />
          </TenantRoute>
        }
      />
      <Route
        path="/register"
        element={
          <TenantRoute>
            <RegisterPage />
          </TenantRoute>
        }
      />
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
