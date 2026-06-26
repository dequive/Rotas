import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    // Provide fallback values for import.meta.env vars used in sync.ts / db.ts
    "import.meta.env.VITE_ROTAS_API_BASE_URL": JSON.stringify("http://localhost:8000"),
    "import.meta.env.VITE_ROTAS_TENANT_ID": JSON.stringify(""),
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
