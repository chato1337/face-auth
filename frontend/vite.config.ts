import path from "node:path"
import { fileURLToPath } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { loadEnv } from "vite"
import { defineConfig } from "vitest/config"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "")
  const port = Number(env.FRONTEND_PORT || process.env.FRONTEND_PORT || 5173)

  return {
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
