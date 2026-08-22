import { useMutation } from "@tanstack/react-query"

import { apiFetch } from "@/api/client"
import type { components } from "@/api/generated/schema"

export type OtpRequestResponse = components["schemas"]["OtpRequestResponse"]
export type OtpVerifyResponse = components["schemas"]["OtpVerifyResponse"]

export type OtpRequestInput = {
  appId: string
  purpose: "email_verify"
  email: string
  firstName: string
  lastName: string
  phone?: string
  channel?: "email"
}

export type OtpVerifyInput = {
  appId: string
  purpose: "email_verify"
  email: string
  code: string
}

export function useOtpRequest() {
  return useMutation({
    mutationFn: async (input: OtpRequestInput) =>
      apiFetch<OtpRequestResponse>("/api/v1/otp/request/", {
        method: "POST",
        appId: input.appId,
        body: JSON.stringify({
          app_id: input.appId,
          purpose: input.purpose,
          channel: input.channel ?? "email",
          email: input.email,
          first_name: input.firstName,
          last_name: input.lastName,
          phone: input.phone ?? "",
        }),
      }),
  })
}

export function useOtpVerify() {
  return useMutation({
    mutationFn: async (input: OtpVerifyInput) =>
      apiFetch<OtpVerifyResponse>("/api/v1/otp/verify/", {
        method: "POST",
        appId: input.appId,
        body: JSON.stringify({
          app_id: input.appId,
          purpose: input.purpose,
          email: input.email,
          code: input.code,
        }),
      }),
  })
}
