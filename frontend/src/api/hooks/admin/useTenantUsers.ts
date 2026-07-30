import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { apiFetch } from "@/api/client"
import type { BiometricProfileAdmin, Paginated, TenantUserAdmin } from "@/api/hooks/admin/types"

export function useAdminTenantUsers(
  appId: string | undefined,
  params?: { q?: string; is_active?: boolean },
) {
  const search = new URLSearchParams()
  if (params?.q) search.set("q", params.q)
  if (params?.is_active !== undefined) search.set("is_active", String(params.is_active))
  const qs = search.toString()

  return useQuery({
    queryKey: ["admin", "users", appId, params ?? {}],
    enabled: Boolean(appId),
    queryFn: () =>
      apiFetch<Paginated<TenantUserAdmin>>(
        `/api/v1/admin/applications/${appId}/users/${qs ? `?${qs}` : ""}`,
        { adminAuth: true },
      ),
  })
}

export function useAdminTenantUser(userId: string | undefined) {
  return useQuery({
    queryKey: ["admin", "user", userId],
    enabled: Boolean(userId),
    queryFn: () =>
      apiFetch<TenantUserAdmin>(`/api/v1/admin/users/${userId}/`, { adminAuth: true }),
  })
}

export function useUpdateTenantUser(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<TenantUserAdmin>) =>
      apiFetch<TenantUserAdmin>(`/api/v1/admin/users/${userId}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
        adminAuth: true,
      }),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "user", userId] })
      void queryClient.invalidateQueries({ queryKey: ["admin", "users", data.app_id] })
    },
  })
}

export function useAdminBiometricProfiles(userId: string | undefined) {
  return useQuery({
    queryKey: ["admin", "biometric-profiles", userId],
    enabled: Boolean(userId),
    queryFn: () =>
      apiFetch<BiometricProfileAdmin[]>(
        `/api/v1/admin/users/${userId}/biometric-profiles/`,
        { adminAuth: true },
      ),
  })
}

export function useUpdateBiometricProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ profileId, is_active }: { profileId: string; is_active: boolean }) =>
      apiFetch<BiometricProfileAdmin>(`/api/v1/admin/biometric-profiles/${profileId}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
        adminAuth: true,
      }),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: ["admin", "biometric-profiles", data.user_id],
      })
    },
  })
}
