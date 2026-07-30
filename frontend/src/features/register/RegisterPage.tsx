import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { AlertCircle, CheckCircle2 } from "lucide-react"

import { ApiError } from "@/api/client"
import { useRegister } from "@/api/hooks/useRegister"
import { CameraCapture } from "@/components/camera/CameraCapture"
import { AuthNavLink, AuthShell } from "@/components/layout/AuthShell"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { useTenant } from "@/context/TenantContext"
import { handleAuthSuccess } from "@/lib/session"

const registerSchema = z.object({
  firstName: z.string().trim().min(1, "Nombre requerido").max(100),
  lastName: z.string().trim().min(1, "Apellido requerido").max(100),
  email: z.email("Correo inválido"),
  phone: z.string().trim().max(30).optional().or(z.literal("")),
})

type RegisterFormValues = z.infer<typeof registerSchema>

export function RegisterPage() {
  const { appId, redirectUri } = useTenant()
  const registerMutation = useRegister()
  const [step, setStep] = useState<"form" | "camera">("form")
  const [apiError, setApiError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [doneLocal, setDoneLocal] = useState(false)

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      firstName: "",
      lastName: "",
      email: "",
      phone: "",
    },
    mode: "onBlur",
  })

  async function onCapture(video: Blob) {
    setApiError(null)
    setFieldError(null)
    const values = form.getValues()

    try {
      const result = await registerMutation.mutateAsync({
        appId,
        firstName: values.firstName.trim(),
        lastName: values.lastName.trim(),
        email: values.email.trim(),
        phone: values.phone?.trim() || "",
        video,
        redirectUri,
      })
      const outcome = handleAuthSuccess(result.tokens)
      if (outcome === "stayed") {
        setDoneLocal(true)
        setStep("form")
      }
    } catch (err) {
      // Regla crítica UX: conservar formulario; solo limpiar video (no guardamos blob).
      if (err instanceof ApiError) {
        setApiError(err.message)
        if (err.field === "email") {
          setFieldError(err.message)
          form.setError("email", { message: err.message })
          setStep("form")
          return
        }
      } else {
        setApiError("No se pudo completar el registro. Inténtalo de nuevo.")
      }
      setStep("camera")
    }
  }

  if (doneLocal) {
    return (
      <AuthShell
        title="Cuenta creada"
        subtitle="Tu perfil biométrico quedó registrado en esta aplicación."
      >
        <Alert className="border-emerald-200 bg-emerald-50 text-emerald-950">
          <CheckCircle2 />
          <AlertTitle>Registro exitoso</AlertTitle>
          <AlertDescription>
            Ya puedes usar el login biométrico en próximos accesos.
          </AlertDescription>
        </Alert>
        <div className="mt-4">
          <AuthNavLink to="/login">Ir a iniciar sesión</AuthNavLink>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title="Crear cuenta"
      subtitle="Completa tus datos y registra tu rostro. Si falla la captura, tus datos se conservan."
      footer={
        <>
          ¿Ya tienes cuenta? <AuthNavLink to="/login">Iniciar sesión</AuthNavLink>
        </>
      }
    >
      {apiError && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle />
          <AlertTitle>No se pudo registrar</AlertTitle>
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      )}

      {registerMutation.isPending ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-white/50 py-16 ring-1 ring-black/5 backdrop-blur-sm">
          <Spinner className="size-8 text-teal-800" />
          <p className="text-sm font-medium text-zinc-800">
            Creando tu perfil biométrico…
          </p>
          <p className="max-w-xs text-center text-xs text-zinc-500">
            Validamos liveness y guardamos tu embedding. Esto puede tardar unos
            segundos.
          </p>
        </div>
      ) : step === "camera" ? (
        <CameraCapture
          onCapture={(blob) => void onCapture(blob)}
          onCancel={() => setStep("form")}
          disabled={registerMutation.isPending}
        />
      ) : (
        <form
          className="flex flex-col gap-5"
          onSubmit={form.handleSubmit(() => {
            setApiError(null)
            setFieldError(null)
            setStep("camera")
          })}
          noValidate
        >
          <FieldGroup>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field data-invalid={!!form.formState.errors.firstName}>
                <FieldLabel htmlFor="firstName">Nombres</FieldLabel>
                <Input
                  id="firstName"
                  autoComplete="given-name"
                  aria-invalid={!!form.formState.errors.firstName}
                  {...form.register("firstName")}
                />
                <FieldError errors={[form.formState.errors.firstName]} />
              </Field>
              <Field data-invalid={!!form.formState.errors.lastName}>
                <FieldLabel htmlFor="lastName">Apellidos</FieldLabel>
                <Input
                  id="lastName"
                  autoComplete="family-name"
                  aria-invalid={!!form.formState.errors.lastName}
                  {...form.register("lastName")}
                />
                <FieldError errors={[form.formState.errors.lastName]} />
              </Field>
            </div>

            <Field data-invalid={!!form.formState.errors.email || !!fieldError}>
              <FieldLabel htmlFor="email">Correo</FieldLabel>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                aria-invalid={!!form.formState.errors.email || !!fieldError}
                {...form.register("email")}
              />
              <FieldError
                errors={[
                  form.formState.errors.email,
                  fieldError ? { message: fieldError } : undefined,
                ]}
              />
            </Field>

            <Field data-invalid={!!form.formState.errors.phone}>
              <FieldLabel htmlFor="phone">Teléfono (opcional)</FieldLabel>
              <Input
                id="phone"
                type="tel"
                autoComplete="tel"
                aria-invalid={!!form.formState.errors.phone}
                {...form.register("phone")}
              />
              <FieldError errors={[form.formState.errors.phone]} />
            </Field>
          </FieldGroup>

          <Button
            type="submit"
            size="lg"
            className="h-11 w-full bg-teal-900 text-teal-50 hover:bg-teal-800"
          >
            Registro biométrico
          </Button>
        </form>
      )}
    </AuthShell>
  )
}
