import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react({ jsxRuntime: "automatic" })],
  oxc: false,
  test: {
    environment: "jsdom",
    globals: true,
    testTimeout: 10_000,
    setupFiles: ["./vitest.setup.ts"],
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**", "**/playwright/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
      "next/server": path.resolve(__dirname, "../../node_modules/next/server.js"),
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
