import { useState } from "react"
import { AlertCircle, CheckCircle2 } from "lucide-react"

import { useLogin } from "@/api/hooks/useLogin"
import { ApiError } from "@/api/client"
import { DashcamCapture } from "@/components/camera/DashcamCapture"
import { AuthNavLink, AuthShell } from "@/components/layout/AuthShell"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useTenant } from "@/context/TenantContext"
import { handleAuthSuccess } from "@/lib/session"

export function LoginPage() {
  const { appId, redirectUri } = useTenant()
  const login = useLogin()
  const [cameraOpen, setCameraOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [doneLocal, setDoneLocal] = useState(false)

  async function onCapture(video: Blob) {
    setError(null)
    try {
      const result = await login.mutateAsync({
        appId,
        video,
        redirectUri,
      })
      const outcome = handleAuthSuccess(result.tokens)
      if (outcome === "stayed") {
        setDoneLocal(true)
        setCameraOpen(false)
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "No se pudo iniciar sesión. Inténtalo de nuevo."
      setError(message)
      setCameraOpen(true)
    }
  }

  if (doneLocal) {
    return (
      <AuthShell
        title="Sesión iniciada"
        subtitle="Tu identidad biométrica fue verificada correctamente."
      >
        <Alert className="border-emerald-200 bg-emerald-50 text-emerald-950">
          <CheckCircle2 />
          <AlertTitle>Listo</AlertTitle>
          <AlertDescription>
            Tokens guardados en esta sesión. Si la app cliente no definió
            redirect_uri, permanece aquí.
          </AlertDescription>
        </Alert>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title="Iniciar sesión"
      subtitle="Usa tu rostro para acceder. No necesitas contraseña."
      footer={
        <>
          ¿Primera vez?{" "}
          <AuthNavLink to="/register">Crear cuenta biométrica</AuthNavLink>
        </>
      }
    >
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle />
          <AlertTitle>No se pudo verificar</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {login.isPending ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-white/50 py-16 ring-1 ring-black/5 backdrop-blur-sm">
          <Spinner className="size-8 text-teal-800" />
          <p className="text-sm font-medium text-zinc-800">
            Analizando tu rostro…
          </p>
          <p className="max-w-xs text-center text-xs text-zinc-500">
            Validamos liveness y comparamos tu biometría. Esto puede tardar unos
            segundos.
          </p>
        </div>
      ) : cameraOpen ? (
        // Si el backend rechaza el intento, la mutación termina, esta rama se
        // vuelve a renderizar y DashcamCapture reinicia la detección sola.
        <DashcamCapture
          onCapture={(blob) => void onCapture(blob)}
          onCancel={() => setCameraOpen(false)}
          disabled={login.isPending}
        />
      ) : (
        <div className="flex flex-col items-stretch gap-4">
          <Button
            type="button"
            size="lg"
            className="h-11 w-full bg-teal-900 text-teal-50 hover:bg-teal-800"
            onClick={() => {
              setError(null)
              setCameraOpen(true)
            }}
          >
            Iniciar sesión con rostro
          </Button>
          <p className="text-center text-xs text-zinc-500">
            La cámara se enciende, detecta tu rostro y captura sola cuando
            parpadees. Sin botones.
          </p>
        </div>
      )}
    </AuthShell>
  )
}
