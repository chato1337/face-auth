import type { components } from "@/api/generated/schema"

export type TokenPair = components["schemas"]["TokenPair"]

const ACCESS_KEY = "faceauth.access"
const REFRESH_KEY = "faceauth.refresh"

export function saveSession(tokens: TokenPair): void {
  sessionStorage.setItem(ACCESS_KEY, tokens.access)
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh)
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY)
}

export function clearSession(): void {
  sessionStorage.removeItem(ACCESS_KEY)
  sessionStorage.removeItem(REFRESH_KEY)
}

/** Redirige al cliente SSO si hay redirect_url; si no, permanece en la app. */
export function handleAuthSuccess(tokens: TokenPair): "redirected" | "stayed" {
  saveSession(tokens)
  if (tokens.redirect_url) {
    const url = new URL(tokens.redirect_url)
    url.searchParams.set("token", tokens.redirect_token)
    window.location.assign(url.toString())
    return "redirected"
  }
  return "stayed"
}
