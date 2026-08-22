import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/api/client"
import {
  useAdminBiometricProfiles,
  useAdminTenantUser,
  useDeleteTenantUser,
  useUpdateBiometricProfile,
  useUpdateTenantUser,
} from "@/api/hooks/admin/useTenantUsers"
import { AdminShell } from "@/components/layout/AdminShell"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

export function TenantUserDetailPage() {
  const { userId = "" } = useParams()
  const navigate = useNavigate()
  const user = useAdminTenantUser(userId)
  const profiles = useAdminBiometricProfiles(userId)
  const updateUser = useUpdateTenantUser(userId)
  const deleteUser = useDeleteTenantUser()
  const updateProfile = useUpdateBiometricProfile()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function toggleActive() {
    if (!user.data) return
    setError(null)
    try {
      await updateUser.mutateAsync({ is_active: !user.data.is_active })
      setMessage(user.data.is_active ? "Usuario desactivado." : "Usuario activado.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar.")
    }
  }

  async function toggleProfile(profileId: string, isActive: boolean) {
    setError(null)
    try {
      await updateProfile.mutateAsync({ profileId, is_active: !isActive })
      setMessage(isActive ? "Perfil biométrico desactivado." : "Perfil biométrico activado.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar el perfil.")
    }
  }

  async function onDelete() {
    if (!user.data) return
    const name = `${user.data.first_name} ${user.data.last_name}`.trim()
    if (
      !window.confirm(
        `¿Eliminar a ${name} y todos sus perfiles biométricos? Esta acción no se puede deshacer.`,
      )
    ) {
      return
    }
    setError(null)
    try {
      const appId = user.data.app_id
      await deleteUser.mutateAsync(userId)
      navigate(`/admin/applications/${appId}/users`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar el usuario.")
    }
  }

  if (user.isLoading) {
    return (
      <AdminShell title="Cargando…">
        <div className="flex justify-center py-16">
          <Spinner className="size-6 text-teal-800" />
        </div>
      </AdminShell>
    )
  }

  if (user.isError || !user.data) {
    return (
      <AdminShell title="Usuario no encontrado">
        <Link to="/admin/applications" className="text-sm text-teal-800 underline">
          Volver
        </Link>
      </AdminShell>
    )
  }

  const u = user.data

  return (
    <AdminShell
      title={`${u.first_name} ${u.last_name}`}
      subtitle={`${u.email} · ${u.app_id}`}
      actions={
        <>
          <Button asChild variant="outline">
            <Link to={`/admin/applications/${u.app_id}/users`}>Usuarios del tenant</Link>
          </Button>
          <Button
            type="button"
            variant={u.is_active ? "destructive" : "default"}
            onClick={toggleActive}
            disabled={updateUser.isPending}
          >
            {u.is_active ? "Desactivar" : "Activar"}
          </Button>
        </>
      }
    >
      <dl className="mb-8 grid max-w-xl gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs tracking-wide text-zinc-500 uppercase">Teléfono</dt>
          <dd className="mt-0.5 text-zinc-800">{u.phone || "—"}</dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-zinc-500 uppercase">Estado</dt>
          <dd className="mt-0.5 text-zinc-800">{u.is_active ? "Activo" : "Inactivo"}</dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-zinc-500 uppercase">Último login</dt>
          <dd className="mt-0.5 text-zinc-800">
            {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Nunca"}
          </dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-zinc-500 uppercase">Creado</dt>
          <dd className="mt-0.5 text-zinc-800">{new Date(u.created_at).toLocaleString()}</dd>
        </div>
      </dl>

      {message ? <p className="mb-4 text-sm text-teal-800">{message}</p> : null}
      {error ? <p className="mb-4 text-sm text-red-700">{error}</p> : null}

      <h2 className="mb-3 text-sm font-semibold tracking-wide text-zinc-700 uppercase">
        Perfiles biométricos
      </h2>

      {profiles.isLoading ? (
        <Spinner className="size-5 text-teal-800" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-teal-950/15 text-xs tracking-wide text-zinc-500 uppercase">
                <th className="py-2 pr-3 font-medium">Modelo</th>
                <th className="py-2 pr-3 font-medium">Liveness</th>
                <th className="py-2 pr-3 font-medium">Calidad</th>
                <th className="py-2 pr-3 font-medium">Estado</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {(profiles.data ?? []).map((p) => (
                <tr key={p.id} className="border-b border-teal-950/8">
                  <td className="py-3 pr-3 font-mono text-xs">{p.model_version}</td>
                  <td className="py-3 pr-3">{p.liveness_score.toFixed(3)}</td>
                  <td className="py-3 pr-3">
                    {p.quality_score != null ? p.quality_score.toFixed(3) : "—"}
                  </td>
                  <td className="py-3 pr-3">
                    <span className={p.is_active ? "text-teal-800" : "text-zinc-400"}>
                      {p.is_active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td className="py-3 text-right">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={updateProfile.isPending}
                      onClick={() => toggleProfile(p.id, p.is_active ?? true)}
                    >
                      {p.is_active ? "Desactivar" : "Activar"}
                    </Button>
                  </td>
                </tr>
              ))}
              {(profiles.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-zinc-500">
                    Sin perfiles biométricos.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      <section className="mt-10 max-w-xl border-t border-red-200 pt-6">
        <h2 className="mb-2 text-sm font-semibold tracking-wide text-red-800 uppercase">
          Zona peligrosa
        </h2>
        <p className="mb-4 text-sm text-zinc-600">
          Elimina el usuario, todos sus embeddings biométricos y el historial de OTP. El email
          quedará libre para un nuevo registro en este tenant. No se puede deshacer.
        </p>
        <Button
          type="button"
          variant="destructive"
          onClick={onDelete}
          disabled={deleteUser.isPending}
        >
          {deleteUser.isPending ? "Eliminando…" : "Eliminar usuario y perfiles"}
        </Button>
      </section>
    </AdminShell>
  )
}
