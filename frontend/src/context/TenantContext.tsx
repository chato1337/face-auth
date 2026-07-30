import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react"
import { Navigate, useSearchParams } from "react-router-dom"

import { ApiError } from "@/api/client"
import {
  useApplication,
  type ApplicationPublic,
} from "@/api/hooks/useApplication"
import { Spinner } from "@/components/ui/spinner"

type TenantContextValue = {
  appId: string
  application: ApplicationPublic
  redirectUri: string | null
}

const TenantContext = createContext<TenantContextValue | null>(null)

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext)
  if (!ctx) {
    throw new Error("useTenant debe usarse dentro de TenantProvider")
  }
  return ctx
}

type TenantProviderProps = {
  children: ReactNode
}

export function TenantProvider({ children }: TenantProviderProps) {
  const [params] = useSearchParams()
  const appId = params.get("app_id")?.trim() || null
  const redirectUri = params.get("redirect_uri")?.trim() || null
  const query = useApplication(appId)

  const value = useMemo<TenantContextValue | null>(() => {
    if (!appId || !query.data) return null
    return {
      appId,
      application: query.data,
      redirectUri,
    }
  }, [appId, query.data, redirectUri])

  if (!appId) {
    return <Navigate to="/404" replace state={{ reason: "missing_app_id" }} />
  }

  if (query.isLoading || query.isFetching) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-3 bg-[radial-gradient(ellipse_at_top,_#e8f1f0_0%,_#f7f6f2_45%,_#eceae4_100%)]">
        <Spinner className="size-6 text-teal-800" />
        <p className="text-sm text-zinc-600">Validando aplicación…</p>
      </div>
    )
  }

  if (query.isError || !query.data) {
    const inactive =
      query.error instanceof ApiError && query.error.code === "app_inactive"
    return (
      <Navigate
        to="/404"
        replace
        state={{
          reason: inactive ? "inactive_app" : "invalid_app",
          appId,
        }}
      />
    )
  }

  if (!value) {
    return null
  }

  return (
    <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
  )
}
