import { withSentryConfig } from "@sentry/nextjs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const managerDir = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: path.resolve(managerDir, "../.."),
  // PR-18: the Manager does not use next/image. Keep the runtime image
  // optimizer disabled so tenant-controlled uploads never reach Sharp/libvips.
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: path.resolve(managerDir, "../.."),
  },
};

// INFRA-01: Wrap with Sentry. Source map upload disabled when SENTRY_AUTH_TOKEN is absent (D-02).
export default withSentryConfig(nextConfig, {
  // Suppress source map upload warnings in local dev
  silent: true,
  // Disable source map upload unless SENTRY_AUTH_TOKEN is set
  disableServerWebpackPlugin: !process.env.SENTRY_AUTH_TOKEN,
  disableClientWebpackPlugin: !process.env.SENTRY_AUTH_TOKEN,
});
