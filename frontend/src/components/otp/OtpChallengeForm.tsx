import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type OtpChallengeFormProps = {
  destinationMasked: string
  expiresIn: number
  isVerifying?: boolean
  isResending?: boolean
  error?: string | null
  onSubmit: (code: string) => void
  onResend: () => void
  onBack: () => void
}

export function OtpChallengeForm({
  destinationMasked,
  expiresIn,
  isVerifying = false,
  isResending = false,
  error = null,
  onSubmit,
  onResend,
  onBack,
}: OtpChallengeFormProps) {
  const [code, setCode] = useState("")
  const [secondsLeft, setSecondsLeft] = useState(expiresIn)

  useEffect(() => {
    setSecondsLeft(expiresIn)
  }, [expiresIn])

  useEffect(() => {
    if (secondsLeft <= 0) return
    const id = window.setTimeout(() => setSecondsLeft((s) => s - 1), 1000)
    return () => window.clearTimeout(id)
  }, [secondsLeft])

  function handleChange(value: string) {
    const digits = value.replace(/\D/g, "").slice(0, 6)
    setCode(digits)
    if (digits.length === 6 && !isVerifying) {
      onSubmit(digits)
    }
  }

  const minutes = Math.floor(Math.max(0, secondsLeft) / 60)
  const seconds = Math.max(0, secondsLeft) % 60
  const ttlLabel = `${minutes}:${String(seconds).padStart(2, "0")}`

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-zinc-600">
        Enviamos un código de 6 dígitos a{" "}
        <span className="font-medium text-zinc-900">{destinationMasked}</span>.
      </p>

      <Field data-invalid={!!error}>
        <FieldLabel htmlFor="otpCode">Código de verificación</FieldLabel>
        <Input
          id="otpCode"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(event) => handleChange(event.target.value)}
          aria-invalid={!!error}
          disabled={isVerifying}
          className="tracking-[0.4em] text-center text-lg font-semibold"
        />
        {error ? <FieldError errors={[{ message: error }]} /> : null}
      </Field>

      <p className="text-xs text-zinc-500">
        {secondsLeft > 0 ? `Caduca en ${ttlLabel}` : "El código expiró. Solicita uno nuevo."}
      </p>

      <Button
        type="button"
        size="lg"
        className="h-11 w-full bg-teal-900 text-teal-50 hover:bg-teal-800"
        disabled={code.length !== 6 || isVerifying}
        onClick={() => onSubmit(code)}
      >
        {isVerifying ? "Validando…" : "Validar código"}
      </Button>

      <div className="flex items-center justify-between text-sm">
        <button
          type="button"
          className="text-zinc-600 underline-offset-4 hover:underline"
          onClick={onBack}
        >
          Volver
        </button>
        <button
          type="button"
          className="text-teal-800 underline-offset-4 hover:underline disabled:text-zinc-400"
          onClick={onResend}
          disabled={isResending}
        >
          {isResending ? "Reenviando…" : "Reenviar código"}
        </button>
      </div>
    </div>
  )
}
