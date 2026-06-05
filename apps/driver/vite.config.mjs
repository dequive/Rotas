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
      // IMPORTANT: 'prompt' — driver controls SKIP_WAITING via banner button.
      // 'autoUpdate' is prohibited: it calls skipWaiting() unconditionally and can
      // reload the app mid-trip (e.g., while a driver is recording delivery proof).
      registerType: "prompt",
      // Manual SW registration in main.tsx via workbox-window for full lifecycle control.
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
        // Enable SW in development mode for local testing
        enabled: true,
        type: "module",
      },
    }),
  ],
  server: {
    port: 5174,
    strictPort: false,
    headers: {
      // CRITICAL: Prevent SW file from being cached by the browser.
      // A cached broken SW is unrecoverable on low-cost Android without clearing all site data.
      // In production (Vercel), this header must be set specifically for /sw.js via vercel.json.
      "Cache-Control": "no-store",
    },
  },
});
