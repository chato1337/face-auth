import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link } from "react-router-dom"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"

import { ApiError } from "@/api/client"
import {
  useAdminApplications,
  useCreateApplication,
} from "@/api/hooks/admin/useApplications"
import { AdminShell } from "@/components/layout/AdminShell"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"

const createSchema = z.object({
  name: z.string().min(1, "Nombre requerido").max(150),
  redirect_uris_text: z.string().optional(),
  liveness_threshold: z.number().min(0).max(1),
  match_threshold: z.number().min(0).max(2),
})

type CreateValues = z.infer<typeof createSchema>

/** URL del SSO hosted para probar el tenant desde el panel. */
function tenantLoginHref(appId: string, redirectUris: unknown): string {
  const params = new URLSearchParams({ app_id: appId })
  if (Array.isArray(redirectUris)) {
    const first = redirectUris.find((u): u is string => typeof u === "string" && u.length > 0)
    if (first) params.set("redirect_uri", first)
  }
  return `/login?${params.toString()}`
}

export function ApplicationsListPage() {
  const [q, setQ] = useState("")
  const [showCreate, setShowCreate] = useState(false)
  const [createdKey, setCreatedKey] = useState<{ appId: string; apiKey: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const apps = useAdminApplications({ q: q || undefined })
  const create = useCreateApplication()

  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: "",
      redirect_uris_text: "http://localhost:3000/callback",
      liveness_threshold: 0.85,
      match_threshold: 0.42,
    },
  })

  async function onCreate(values: CreateValues) {
    setError(null)
    setCreatedKey(null)
    const redirect_uris = (values.redirect_uris_text ?? "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
    try {
      const result = await create.mutateAsync({
        name: values.name,
        redirect_uris,
        liveness_threshold: values.liveness_threshold,
        match_threshold: values.match_threshold,
        is_active: true,
      })
      setCreatedKey({ appId: result.app_id, apiKey: result.api_key })
      form.reset()
      setShowCreate(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el tenant.")
    }
  }

  return (
    <AdminShell
      title="Applications"
      subtitle="Tenants que consumen el SSO biométrico."
      actions={
        <Button type="button" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? "Cancelar" : "Nuevo tenant"}
        </Button>
      }
    >
      {createdKey ? (
        <Alert className="mb-6 border-amber-200 bg-amber-50 text-amber-950">
          <AlertTitle>API key (cópiala ahora)</AlertTitle>
          <AlertDescription>
            <p className="mb-1 font-mono text-xs">app_id: {createdKey.appId}</p>
            <p className="font-mono text-xs break-all">{createdKey.apiKey}</p>
            <p className="mt-2 text-xs opacity-80">
              No se volverá a mostrar en listados. Guárdala en el gestor de secretos.
            </p>
          </AlertDescription>
        </Alert>
      ) : null}

      {showCreate ? (
        <form
          onSubmit={form.handleSubmit(onCreate)}
          className="mb-8 space-y-3 border-b border-teal-950/10 pb-8"
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="name">Nombre</Label>
              <Input id="name" {...form.register("name")} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="redirect_uris_text">Redirect URIs (una por línea)</Label>
              <Textarea id="redirect_uris_text" rows={3} {...form.register("redirect_uris_text")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="liveness_threshold">Liveness threshold</Label>
              <Input
                id="liveness_threshold"
                type="number"
                step="0.01"
                {...form.register("liveness_threshold", { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="match_threshold">Match threshold</Label>
              <Input
                id="match_threshold"
                type="number"
                step="0.01"
                {...form.register("match_threshold", { valueAsNumber: true })}
              />
            </div>
          </div>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? <Spinner data-icon="inline-start" /> : null}
            Crear
          </Button>
        </form>
      ) : null}

      <div className="mb-4">
        <Input
          placeholder="Buscar por nombre o app_id…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {apps.isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner className="size-6 text-teal-800" />
        </div>
      ) : apps.isError ? (
        <p className="text-sm text-red-700">No se pudo cargar el listado.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-teal-950/15 text-xs tracking-wide text-zinc-500 uppercase">
                <th className="py-2 pr-3 font-medium">Nombre</th>
                <th className="py-2 pr-3 font-medium">app_id</th>
                <th className="py-2 pr-3 font-medium">Estado</th>
                <th className="py-2 pr-3 font-medium">Usuarios</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {(apps.data?.results ?? []).map((app) => (
                <tr key={app.app_id} className="border-b border-teal-950/8">
                  <td className="py-3 pr-3 font-medium text-zinc-900">{app.name}</td>
                  <td className="py-3 pr-3 font-mono text-xs text-zinc-600">{app.app_id}</td>
                  <td className="py-3 pr-3">
                    <span
                      className={
                        app.is_active
                          ? "text-teal-800"
                          : "text-zinc-400"
                      }
                    >
                      {app.is_active ? "Activa" : "Inactiva"}
                    </span>
                  </td>
                  <td className="py-3 pr-3 text-zinc-600">{app.users_count ?? 0}</td>
                  <td className="py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button asChild variant="outline" size="sm">
                        <a
                          href={tenantLoginHref(app.app_id, app.redirect_uris)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Ir al login
                        </a>
                      </Button>
                      <Button asChild variant="ghost" size="sm">
                        <Link to={`/admin/applications/${app.app_id}`}>Abrir</Link>
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {(apps.data?.results ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-zinc-500">
                    No hay tenants. Crea el primero.
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
