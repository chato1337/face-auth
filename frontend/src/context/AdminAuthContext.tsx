import { createContext, useContext, type ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

import { useAdminMe } from "@/api/hooks/admin/useAdminAuth"
import { Spinner } from "@/components/ui/spinner"
import { hasAdminSession } from "@/lib/adminSession"

type AdminAuthContextValue = {
  username: string
  email: string
  isSuperuser: boolean
}

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

export function useAdminAuth(): AdminAuthContextValue {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) {
    throw new Error("useAdminAuth debe usarse dentro de AdminAuthProvider")
  }
  return ctx
}

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const hasSession = hasAdminSession()
  const me = useAdminMe(hasSession)

  if (!hasSession) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
  }

  if (me.isLoading) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-zinc-100">
        <Spinner className="size-6 text-teal-800" />
      </div>
    )
  }

  if (me.isError || !me.data) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
  }

  return (
    <AdminAuthContext.Provider
      value={{
        username: me.data.username,
        email: me.data.email,
        isSuperuser: me.data.is_superuser,
      }}
    >
      {children}
    </AdminAuthContext.Provider>
  )
}
