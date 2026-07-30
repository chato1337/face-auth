import { useMutation } from "@tanstack/react-query"

import { apiMultipart } from "@/api/client"
import type { components } from "@/api/generated/schema"

export type LoginResponse = components["schemas"]["LoginResponse"]

export type LoginInput = {
  appId: string
  video: Blob
  redirectUri?: string | null
}

export function useLogin() {
  return useMutation({
    mutationFn: async ({ appId, video, redirectUri }: LoginInput) => {
      const form = new FormData()
      form.append("app_id", appId)
      form.append("video", video, "capture.webm")
      if (redirectUri) {
        form.append("redirect_uri", redirectUri)
      }
      return apiMultipart<LoginResponse>("/api/v1/auth/login/", form, { appId })
    },
  })
}
