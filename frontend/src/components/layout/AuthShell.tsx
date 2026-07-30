import { Link } from "react-router-dom"
import type { ReactNode } from "react"

import { useTenant } from "@/context/TenantContext"
import { cn } from "@/lib/utils"

type AuthShellProps = {
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
  className?: string
}

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  className,
}: AuthShellProps) {
  const { application, appId } = useTenant()

  return (
    <div className="relative min-h-svh overflow-hidden bg-[radial-gradient(ellipse_at_top,_#dfeceb_0%,_#f4f2ec_42%,_#e7e4dc_100%)]">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%230f766e' fill-opacity='0.06'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        }}
      />

      <div className="relative mx-auto flex min-h-svh w-full max-w-lg flex-col px-5 py-8 sm:px-6 sm:py-12">
        <header className="mb-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
          <p className="font-heading text-3xl font-semibold tracking-tight text-teal-950 sm:text-4xl">
            Face-Auth
          </p>
          <p className="mt-1 text-sm text-teal-900/70">
            Acceso biométrico · {application.name}
          </p>
        </header>

        <main
          className={cn(
            "animate-in fade-in slide-in-from-bottom-3 flex flex-1 flex-col duration-700",
            className,
          )}
        >
          <h1 className="text-xl font-semibold tracking-tight text-zinc-900 sm:text-2xl">
            {title}
          </h1>
          <p className="mt-2 max-w-prose text-sm leading-relaxed text-zinc-600">
            {subtitle}
          </p>
          <div className="mt-6 flex flex-1 flex-col">{children}</div>
        </main>

        {footer ? <footer className="mt-8 text-sm text-zinc-500">{footer}</footer> : null}

        <p className="mt-6 text-center text-[11px] tracking-wide text-zinc-400 uppercase">
          app_id · {appId}
        </p>
      </div>
    </div>
  )
}

type AuthNavLinkProps = {
  to: string
  children: ReactNode
}

export function AuthNavLink({ to, children }: AuthNavLinkProps) {
  const { appId, redirectUri } = useTenant()
  const params = new URLSearchParams({ app_id: appId })
  if (redirectUri) params.set("redirect_uri", redirectUri)

  return (
    <Link
      to={`${to}?${params.toString()}`}
      className="font-medium text-teal-800 underline-offset-4 hover:underline"
    >
      {children}
    </Link>
  )
}
