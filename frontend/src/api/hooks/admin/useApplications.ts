import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { apiFetch } from "@/api/client"
import type {
  ApplicationAdmin,
  ApplicationAdminCreate,
  ApplicationCreated,
  ApplicationRotateApiKey,
  Paginated,
} from "@/api/hooks/admin/types"

export function useAdminApplications(params?: { q?: string; is_active?: boolean }) {
  const search = new URLSearchParams()
  if (params?.q) search.set("q", params.q)
  if (params?.is_active !== undefined) search.set("is_active", String(params.is_active))
  const qs = search.toString()

  return useQuery({
    queryKey: ["admin", "applications", params ?? {}],
    queryFn: () =>
      apiFetch<Paginated<ApplicationAdmin>>(
        `/api/v1/admin/applications/${qs ? `?${qs}` : ""}`,
        { adminAuth: true },
      ),
  })
}

export function useAdminApplication(appId: string | undefined) {
  return useQuery({
    queryKey: ["admin", "applications", appId],
    enabled: Boolean(appId),
    queryFn: () =>
      apiFetch<ApplicationAdmin>(`/api/v1/admin/applications/${appId}/`, {
        adminAuth: true,
      }),
  })
}

export function useCreateApplication() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ApplicationAdminCreate) =>
      apiFetch<ApplicationCreated>("/api/v1/admin/applications/", {
        method: "POST",
        body: JSON.stringify(body),
        adminAuth: true,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "applications"] })
    },
  })
}

export function useUpdateApplication(appId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<ApplicationAdmin>) =>
      apiFetch<ApplicationAdmin>(`/api/v1/admin/applications/${appId}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
        adminAuth: true,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "applications"] })
    },
  })
}

export function useRotateApiKey(appId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<ApplicationRotateApiKey>(
        `/api/v1/admin/applications/${appId}/rotate-api-key/`,
        { method: "POST", adminAuth: true },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "applications", appId] })
    },
  })
}
