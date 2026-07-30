import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { AlertCircle } from "lucide-react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { z } from "zod"

import { ApiError } from "@/api/client"
import { useAdminLogin } from "@/api/hooks/admin/useAdminAuth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { hasAdminSession } from "@/lib/adminSession"

const schema = z.object({
  username: z.string().min(1, "Usuario requerido"),
  password: z.string().min(1, "Contraseña requerida"),
})

type FormValues = z.infer<typeof schema>

export function AdminLoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const login = useAdminLogin()
  const [error, setError] = useState<string | null>(null)
  const from = (location.state as { from?: string } | null)?.from ?? "/admin/applications"

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: "", password: "" },
  })

  if (hasAdminSession()) {
    return <Navigate to="/admin/applications" replace />
  }

  async function onSubmit(values: FormValues) {
    setError(null)
    try {
      await login.mutateAsync(values)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "not_superuser") {
          setError("Solo usuarios superuser pueden acceder al panel.")
        } else {
          setError(err.message)
        }
      } else {
        setError("No se pudo iniciar sesión.")
      }
    }
  }

  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[radial-gradient(ellipse_at_top,_#dfeceb_0%,_#f4f2ec_42%,_#e7e4dc_100%)] px-5">
      <div className="relative w-full max-w-md animate-in fade-in slide-in-from-bottom-3 duration-700">
        <p className="font-heading text-3xl font-semibold tracking-tight text-teal-950">
          Face-Auth
        </p>
        <p className="mt-1 text-sm text-teal-900/70">Panel de administración</p>

        <h1 className="mt-8 text-xl font-semibold text-zinc-900">Iniciar sesión</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Acceso restringido a operadores Django con <code className="text-xs">is_superuser</code>.
        </p>

        <form className="mt-6 space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="username">Usuario</Label>
            <Input id="username" autoComplete="username" {...form.register("username")} />
            {form.formState.errors.username ? (
              <p className="text-xs text-red-700">{form.formState.errors.username.message}</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Contraseña</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...form.register("password")}
            />
            {form.formState.errors.password ? (
              <p className="text-xs text-red-700">{form.formState.errors.password.message}</p>
            ) : null}
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertTitle>Acceso denegado</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <Button type="submit" className="w-full" disabled={login.isPending} size="lg">
            {login.isPending ? <Spinner data-icon="inline-start" /> : null}
            Entrar
          </Button>
        </form>
      </div>
    </div>
  )
}
