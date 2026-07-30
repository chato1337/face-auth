const ACCESS_KEY = "faceauth.admin.access"
const REFRESH_KEY = "faceauth.admin.refresh"
const USERNAME_KEY = "faceauth.admin.username"

export type AdminTokenPair = {
  access: string
  refresh: string
}

export function saveAdminSession(tokens: AdminTokenPair, username?: string): void {
  sessionStorage.setItem(ACCESS_KEY, tokens.access)
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh)
  if (username) {
    sessionStorage.setItem(USERNAME_KEY, username)
  }
}

export function getAdminAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY)
}

export function getAdminRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY)
}

export function getAdminUsername(): string | null {
  return sessionStorage.getItem(USERNAME_KEY)
}

export function clearAdminSession(): void {
  sessionStorage.removeItem(ACCESS_KEY)
  sessionStorage.removeItem(REFRESH_KEY)
  sessionStorage.removeItem(USERNAME_KEY)
}

export function hasAdminSession(): boolean {
  return Boolean(getAdminAccessToken())
}
