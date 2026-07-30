import type { components } from "@/api/generated/schema"
import {
  clearAdminSession,
  getAdminAccessToken,
  getAdminRefreshToken,
  saveAdminSession,
} from "@/lib/adminSession"

export type ApiErrorBody = components["schemas"]["ErrorResponse"]

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly field: string | null

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = "ApiError"
    this.status = status
    this.code = body.code
    this.field = body.field ?? null
  }
}

const DEFAULT_BASE = "http://localhost:8000"

export function getApiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "")
    ?? DEFAULT_BASE
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = {
    code: "unknown_error",
    message: response.statusText || "Error inesperado del servidor.",
    field: null,
  }
  try {
    const json = (await response.json()) as Partial<ApiErrorBody>
    if (json.code && json.message) {
      body = {
        code: json.code,
        message: json.message,
        field: json.field ?? null,
      }
    } else if (typeof json === "object" && json !== null) {
      const entries = Object.entries(json as Record<string, unknown>)
      const first = entries[0]
      if (first) {
        const [field, value] = first
        const message = Array.isArray(value)
          ? String(value[0])
          : typeof value === "string"
            ? value
            : "Datos inválidos."
        body = { code: "validation_error", message, field }
      }
    }
  } catch {
    // keep default body
  }
  return new ApiError(response.status, body)
}

export type ApiFetchOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | null
  appId?: string
  /** Adjunta Bearer del operador admin y reintenta con refresh ante 401. */
  adminAuth?: boolean
}

let refreshInFlight: Promise<boolean> | null = null

async function refreshAdminAccessToken(): Promise<boolean> {
  const refresh = getAdminRefreshToken()
  if (!refresh) return false

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/v1/admin/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
        })
        if (!response.ok) {
          clearAdminSession()
          return false
        }
        const data = (await response.json()) as { access: string; refresh?: string }
        saveAdminSession({
          access: data.access,
          refresh: data.refresh ?? refresh,
        })
        return true
      } catch {
        clearAdminSession()
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }

  return refreshInFlight
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { appId, adminAuth, headers: initHeaders, ...rest } = options
  const headers = new Headers(initHeaders)

  if (appId) {
    headers.set("X-App-Id", appId)
  }

  if (adminAuth) {
    const access = getAdminAccessToken()
    if (access) {
      headers.set("Authorization", `Bearer ${access}`)
    }
  }

  if (rest.body && !(rest.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  let response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...rest,
    headers,
  })

  if (adminAuth && response.status === 401) {
    const refreshed = await refreshAdminAccessToken()
    if (refreshed) {
      const retryHeaders = new Headers(initHeaders)
      if (appId) retryHeaders.set("X-App-Id", appId)
      const newAccess = getAdminAccessToken()
      if (newAccess) retryHeaders.set("Authorization", `Bearer ${newAccess}`)
      if (rest.body && !(rest.body instanceof FormData) && !retryHeaders.has("Content-Type")) {
        retryHeaders.set("Content-Type", "application/json")
      }
      response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...rest,
        headers: retryHeaders,
      })
    }
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function apiMultipart<T>(
  path: string,
  formData: FormData,
  options: { appId?: string; method?: string } = {},
): Promise<T> {
  return apiFetch<T>(path, {
    method: options.method ?? "POST",
    body: formData,
    appId: options.appId,
  })
}
