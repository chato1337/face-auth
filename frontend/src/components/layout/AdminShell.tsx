import { Link, NavLink, useNavigate } from "react-router-dom"
import type { ReactNode } from "react"

import { useAdminLogout } from "@/api/hooks/admin/useAdminAuth"
import { Button } from "@/components/ui/button"
import { useAdminAuth } from "@/context/AdminAuthContext"
import { cn } from "@/lib/utils"

type AdminShellProps = {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}

export function AdminShell({ title, subtitle, actions, children }: AdminShellProps) {
  const { username } = useAdminAuth()
  const logout = useAdminLogout()
  const navigate = useNavigate()

  return (
    <div className="min-h-svh bg-[linear-gradient(165deg,#e8f0ef_0%,#f3f1eb_48%,#ebe6dc_100%)]">
      <header className="border-b border-teal-950/10 bg-white/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link to="/admin/applications" className="font-heading text-lg font-semibold text-teal-950">
              Face-Auth
              <span className="ml-2 text-xs font-normal tracking-wide text-teal-800/60 uppercase">
                Admin
              </span>
            </Link>
            <nav className="hidden items-center gap-1 sm:flex">
              <NavLink
                to="/admin/applications"
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-1.5 text-sm transition-colors",
                    isActive
                      ? "bg-teal-900/10 font-medium text-teal-950"
                      : "text-zinc-600 hover:bg-teal-900/5 hover:text-teal-900",
                  )
                }
              >
                Applications
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-zinc-500 sm:inline">{username}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                logout()
                navigate("/admin/login", { replace: true })
              }}
            >
              Salir
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8 sm:px-6">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">{title}</h1>
            {subtitle ? (
              <p className="mt-1 max-w-2xl text-sm leading-relaxed text-zinc-600">{subtitle}</p>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
        </div>
        <div className="animate-in fade-in slide-in-from-bottom-3 duration-700">{children}</div>
      </main>
    </div>
  )
}
