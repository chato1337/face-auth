import type { components } from "@/api/generated/schema"

export type AdminLoginResponse = components["schemas"]["AdminLoginResponse"]
export type AdminMe = components["schemas"]["AdminMe"]
export type ApplicationAdmin = components["schemas"]["ApplicationAdmin"]
export type ApplicationCreated = components["schemas"]["ApplicationCreated"]
export type ApplicationAdminCreate = components["schemas"]["ApplicationAdminCreateRequest"]
export type ApplicationRotateApiKey = components["schemas"]["ApplicationRotateApiKey"]
export type TenantUserAdmin = components["schemas"]["TenantUserAdmin"]
export type BiometricProfileAdmin = components["schemas"]["BiometricProfileAdmin"]

export type Paginated<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
