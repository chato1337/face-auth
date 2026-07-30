import { useState } from "react"
import { Link, useParams } from "react-router-dom"

import { useAdminApplication } from "@/api/hooks/admin/useApplications"
import { useAdminTenantUsers } from "@/api/hooks/admin/useTenantUsers"
import { AdminShell } from "@/components/layout/AdminShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"

export function TenantUsersListPage() {
  const { appId = "" } = useParams()
  const [q, setQ] = useState("")
  const app = useAdminApplication(appId)
  const users = useAdminTenantUsers(appId, { q: q || undefined })

  return (
    <AdminShell
      title="Usuarios"
      subtitle={app.data ? `${app.data.name} · ${appId}` : appId}
      actions={
        <Button asChild variant="outline">
          <Link to={`/admin/applications/${appId}`}>Volver al tenant</Link>
        </Button>
      }
    >
      <div className="mb-4">
        <Input
          placeholder="Buscar por nombre o email…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {users.isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner className="size-6 text-teal-800" />
        </div>
      ) : users.isError ? (
        <p className="text-sm text-red-700">No se pudo cargar usuarios.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-teal-950/15 text-xs tracking-wide text-zinc-500 uppercase">
                <th className="py-2 pr-3 font-medium">Nombre</th>
                <th className="py-2 pr-3 font-medium">Email</th>
                <th className="py-2 pr-3 font-medium">Estado</th>
                <th className="py-2 pr-3 font-medium">Perfiles</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {(users.data?.results ?? []).map((user) => (
                <tr key={user.id} className="border-b border-teal-950/8">
                  <td className="py-3 pr-3 font-medium text-zinc-900">
                    {user.first_name} {user.last_name}
                  </td>
                  <td className="py-3 pr-3 text-zinc-600">{user.email}</td>
                  <td className="py-3 pr-3">
                    <span className={user.is_active ? "text-teal-800" : "text-zinc-400"}>
                      {user.is_active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td className="py-3 pr-3 text-zinc-600">
                    {user.active_profiles_count ?? 0}
                  </td>
                  <td className="py-3 text-right">
                    <Link
                      to={`/admin/users/${user.id}`}
                      className="font-medium text-teal-800 underline-offset-4 hover:underline"
                    >
                      Abrir
                    </Link>
                  </td>
                </tr>
              ))}
              {(users.data?.results ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-zinc-500">
                    Sin usuarios en este tenant. El alta sigue siendo el flujo biométrico de registro.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}
    </AdminShell>
  )
}
