import { sentryVitePlugin } from "@sentry/vite-plugin";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  cacheDir: "../../node_modules/.vite/driver",
  plugins: [
    react(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      // The driver explicitly controls activation so an update cannot reload
      // the application while a trip or delivery proof is being recorded.
      registerType: "prompt",
      injectRegister: false,
      manifest: {
        name: "ROTAS Motorista",
        short_name: "Motorista",
        description: "ROTAS — Gestão de frotas e viagens offline-first para motoristas",
        display: "standalone",
        start_url: "/",
        scope: "/",
        theme_color: "#102033",
        background_color: "#f5f7fa",
        lang: "pt",
        orientation: "portrait-primary",
        icons: [
          {
            src: "/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any maskable",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      devOptions: {
        enabled: true,
        type: "module",
      },
    }),
    ...(process.env.SENTRY_AUTH_TOKEN
      ? [
          sentryVitePlugin({
            org: process.env.SENTRY_ORG ?? "",
            project: process.env.SENTRY_PROJECT ?? "rotas",
            authToken: process.env.SENTRY_AUTH_TOKEN,
            telemetry: false,
          }),
        ]
      : []),
  ],
  build: {
    sourcemap: true,
  },
  server: {
    port: 5174,
    strictPort: false,
    headers: {
      "Cache-Control": "no-store",
    },
  },
});
