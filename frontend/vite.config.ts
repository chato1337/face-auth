import path from "node:path"
import { fileURLToPath } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { loadEnv } from "vite"
import { defineConfig } from "vitest/config"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
/** `.env` del monorepo (fuente de verdad para VITE_* y FRONTEND_PORT). */
const monorepoEnvDir = path.resolve(__dirname, "..")

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Prioridad: process.env (Compose) > .env raíz > frontend/.env (fallback local)
  const rootEnv = loadEnv(mode, monorepoEnvDir, "")
  const localEnv = loadEnv(mode, __dirname, "")
  const port = Number(
    process.env.FRONTEND_PORT ||
      rootEnv.FRONTEND_PORT ||
      localEnv.FRONTEND_PORT ||
      5173,
  )

  return {
    envDir: monorepoEnvDir,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: true,
      port,
      strictPort: true,
    },
    preview: {
      host: true,
      port,
      strictPort: true,
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: true,
    },
  }
})
