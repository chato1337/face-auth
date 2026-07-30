import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { apiFetch } from "@/api/client"
import type { AdminLoginResponse, AdminMe } from "@/api/hooks/admin/types"
import { clearAdminSession, saveAdminSession } from "@/lib/adminSession"

export const adminMeQueryKey = ["admin", "me"] as const

export function useAdminMe(enabled = true) {
  return useQuery({
    queryKey: adminMeQueryKey,
    enabled,
    queryFn: () => apiFetch<AdminMe>("/api/v1/admin/auth/me/", { adminAuth: true }),
    retry: false,
  })
}

export function useAdminLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { username: string; password: string }) =>
      apiFetch<AdminLoginResponse>("/api/v1/admin/auth/login/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      saveAdminSession({ access: data.access, refresh: data.refresh }, data.username)
      void queryClient.invalidateQueries({ queryKey: adminMeQueryKey })
    },
  })
}

export function useAdminLogout() {
  const queryClient = useQueryClient()
  return () => {
    clearAdminSession()
    queryClient.removeQueries({ queryKey: ["admin"] })
  }
}
