import type { ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { AdminAuthProvider } from "@/context/AdminAuthContext"
import { TenantProvider } from "@/context/TenantContext"
import { AdminLoginPage } from "@/features/admin/AdminLoginPage"
import { ApplicationDetailPage } from "@/features/admin/applications/ApplicationDetailPage"
import { ApplicationsListPage } from "@/features/admin/applications/ApplicationsListPage"
import { TenantUserDetailPage } from "@/features/admin/users/TenantUserDetailPage"
import { TenantUsersListPage } from "@/features/admin/users/TenantUsersListPage"
import { LoginPage } from "@/features/login/LoginPage"
import { NotFoundPage } from "@/features/not-found/NotFoundPage"
import { RegisterPage } from "@/features/register/RegisterPage"

function TenantRoute({ children }: { children: ReactNode }) {
  return <TenantProvider>{children}</TenantProvider>
}

function AdminRoute({ children }: { children: ReactNode }) {
  return <AdminAuthProvider>{children}</AdminAuthProvider>
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

      <Route path="/admin" element={<Navigate to="/admin/applications" replace />} />
      <Route path="/admin/login" element={<AdminLoginPage />} />
      <Route
        path="/admin/applications"
        element={
          <AdminRoute>
            <ApplicationsListPage />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/applications/:appId"
        element={
          <AdminRoute>
            <ApplicationDetailPage />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/applications/:appId/users"
        element={
          <AdminRoute>
            <TenantUsersListPage />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/users/:userId"
        element={
          <AdminRoute>
            <TenantUserDetailPage />
          </AdminRoute>
        }
      />

      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
