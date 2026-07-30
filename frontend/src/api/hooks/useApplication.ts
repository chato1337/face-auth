import { useQuery } from "@tanstack/react-query"

import { apiFetch } from "@/api/client"
import type { components } from "@/api/generated/schema"

export type ApplicationPublic = components["schemas"]["ApplicationPublic"]

export function useApplication(appId: string | null) {
  return useQuery({
    queryKey: ["application", appId],
    enabled: Boolean(appId),
    queryFn: () =>
      apiFetch<ApplicationPublic>(
        `/api/v1/applications/${encodeURIComponent(appId!)}/`,
      ),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}
