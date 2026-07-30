import type { components } from "@/api/generated/schema"

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
      // DRF validation errors: { field: ["msg"] }
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
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { appId, headers: initHeaders, ...rest } = options
  const headers = new Headers(initHeaders)

  if (appId) {
    headers.set("X-App-Id", appId)
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...rest,
    headers,
  })

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
