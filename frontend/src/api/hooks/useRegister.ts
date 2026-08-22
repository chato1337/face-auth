import { useMutation } from "@tanstack/react-query"

import { apiMultipart } from "@/api/client"
import type { components } from "@/api/generated/schema"

export type RegisterResponse = components["schemas"]["RegisterResponse"]

export type RegisterInput = {
  appId: string
  firstName: string
  lastName: string
  email: string
  phone?: string
  video: Blob
  otpCode: string
  redirectUri?: string | null
}

export function useRegister() {
  return useMutation({
    mutationFn: async (input: RegisterInput) => {
      const form = new FormData()
      form.append("app_id", input.appId)
      form.append("first_name", input.firstName)
      form.append("last_name", input.lastName)
      form.append("email", input.email)
      form.append("phone", input.phone ?? "")
      form.append("video", input.video, "capture.webm")
      form.append("otp_code", input.otpCode)
      if (input.redirectUri) {
        form.append("redirect_uri", input.redirectUri)
      }
      return apiMultipart<RegisterResponse>("/api/v1/auth/register/", form, {
        appId: input.appId,
      })
    },
  })
}
