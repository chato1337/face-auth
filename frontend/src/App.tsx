import { Button } from "@/components/ui/button"

export default function App() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 bg-background p-8 text-foreground">
      <h1 className="text-3xl font-semibold tracking-tight">Face-Auth</h1>
      <p className="max-w-md text-center text-muted-foreground">
        Frontend scaffold (Fase 1). Los flujos de login y registro llegan en la
        Fase 4.
      </p>
      <Button type="button">Listo</Button>
    </main>
  )
}
