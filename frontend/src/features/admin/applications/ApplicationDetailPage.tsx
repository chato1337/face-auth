import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useParams } from "react-router-dom"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"

import { ApiError } from "@/api/client"
import {
  useAdminApplication,
  useRotateApiKey,
  useUpdateApplication,
} from "@/api/hooks/admin/useApplications"
import { AdminShell } from "@/components/layout/AdminShell"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { parseRedirectUris, urisToText } from "@/lib/redirectUris"

const editSchema = z.object({
  name: z.string().min(1).max(150),
  is_active: z.boolean(),
  redirect_uris_text: z.string(),
  liveness_threshold: z.number().min(0).max(1),
  match_threshold: z.number().min(0).max(2),
})

type EditValues = z.infer<typeof editSchema>

export function ApplicationDetailPage() {
  const { appId = "" } = useParams()
  const app = useAdminApplication(appId)
  const update = useUpdateApplication(appId)
  const rotate = useRotateApiKey(appId)
  const [oneShotKey, setOneShotKey] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    values: app.data
      ? {
          name: app.data.name,
          is_active: app.data.is_active ?? true,
          redirect_uris_text: urisToText(app.data.redirect_uris),
          liveness_threshold: app.data.liveness_threshold ?? 0.85,
          match_threshold: app.data.match_threshold ?? 0.42,
        }
      : undefined,
  })

  async function onSave(values: EditValues) {
    setError(null)
    setMessage(null)
    try {
      await update.mutateAsync({
        name: values.name,
        is_active: values.is_active,
        redirect_uris: parseRedirectUris(values.redirect_uris_text),
        liveness_threshold: values.liveness_threshold,
        match_threshold: values.match_threshold,
      })
      setMessage("Cambios guardados.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.")
    }
  }

  async function onRotate() {
    if (!window.confirm("¿Rotar la api_key? La anterior quedará inválida de inmediato.")) {
      return
    }
    setError(null)
    try {
      const result = await rotate.mutateAsync()
      setOneShotKey(result.api_key)
      setMessage("API key rotada.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo rotar la clave.")
    }
  }

  if (app.isLoading) {
    return (
      <AdminShell title="Cargando…">
        <div className="flex justify-center py-16">
          <Spinner className="size-6 text-teal-800" />
        </div>
      </AdminShell>
    )
  }

  if (app.isError || !app.data) {
    return (
      <AdminShell title="Tenant no encontrado">
        <Link to="/admin/applications" className="text-sm text-teal-800 underline">
          Volver al listado
        </Link>
      </AdminShell>
    )
  }

  return (
    <AdminShell
      title={app.data.name}
      subtitle={app.data.app_id}
      actions={
        <>
          <Button asChild variant="outline">
            <Link to={`/admin/applications/${appId}/users`}>Usuarios</Link>
          </Button>
          <Button type="button" variant="destructive" onClick={onRotate} disabled={rotate.isPending}>
            Rotar API key
          </Button>
        </>
      }
    >
      {oneShotKey ? (
        <Alert className="mb-6 border-amber-200 bg-amber-50 text-amber-950">
          <AlertTitle>Nueva API key (una sola vez)</AlertTitle>
          <AlertDescription>
            <p className="font-mono text-xs break-all">{oneShotKey}</p>
          </AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={form.handleSubmit(onSave)} className="max-w-xl space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">Nombre</Label>
          <Input id="name" {...form.register("name")} />
        </div>
        <div className="flex items-center gap-2">
          <input
            id="is_active"
            type="checkbox"
            className="size-4 accent-teal-800"
            {...form.register("is_active")}
          />
          <Label htmlFor="is_active">Activa</Label>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="redirect_uris_text">Redirect URIs (una por línea o separadas por coma)</Label>
          <Textarea id="redirect_uris_text" rows={4} {...form.register("redirect_uris_text")} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
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

        {message ? <p className="text-sm text-teal-800">{message}</p> : null}
        {error ? <p className="text-sm text-red-700">{error}</p> : null}

        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? <Spinner data-icon="inline-start" /> : null}
          Guardar
        </Button>
      </form>

      <p className="mt-8 text-xs text-zinc-500">
        Última rotación de api_key:{" "}
        {app.data.api_key_rotated_at
          ? new Date(app.data.api_key_rotated_at).toLocaleString()
          : "nunca (clave de creación)"}
      </p>
    </AdminShell>
  )
}
