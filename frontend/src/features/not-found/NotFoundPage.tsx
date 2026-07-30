import { useLocation, Link } from "react-router-dom"

type NotFoundState = {
  reason?: "missing_app_id" | "invalid_app" | "inactive_app"
  appId?: string
}

const MESSAGES: Record<NonNullable<NotFoundState["reason"]>, string> = {
  missing_app_id:
    "Falta el parámetro app_id en la URL. Las apps cliente deben abrir Face-Auth con ?app_id=…",
  invalid_app: "No existe una aplicación con ese app_id.",
  inactive_app: "Esta aplicación está desactivada y no puede autenticar usuarios.",
}

export function NotFoundPage() {
  const location = useLocation()
  const state = (location.state as NotFoundState | null) ?? {}
  const message =
    (state.reason && MESSAGES[state.reason]) ||
    "La página que buscas no existe o el tenant no es válido."

  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[radial-gradient(ellipse_at_top,_#e4ebe9_0%,_#f4f2ec_50%,_#e7e4dc_100%)] px-5">
      <div className="relative w-full max-w-md animate-in fade-in slide-in-from-bottom-2 duration-500">
        <p className="font-heading text-3xl font-semibold tracking-tight text-teal-950">
          Face-Auth
        </p>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight text-zinc-900">
          No encontrado
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600">{message}</p>
        {state.appId ? (
          <p className="mt-3 font-mono text-xs text-zinc-400">{state.appId}</p>
        ) : null}
        <p className="mt-8 text-sm text-zinc-500">
          Ejemplo:{" "}
          <code className="rounded bg-black/5 px-1.5 py-0.5 text-xs">
            /login?app_id=app_xxxxx
          </code>
        </p>
        <Link
          to="/login"
          className="mt-6 inline-block text-sm font-medium text-teal-800 underline-offset-4 hover:underline"
        >
          Volver al login
        </Link>
      </div>
    </div>
  )
}
