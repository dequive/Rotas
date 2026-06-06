import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Safe fallback for Next.js 14.2.x — some patch versions need this flag
  // to auto-discover instrumentation.ts at project root.
  experimental: {
    instrumentationHook: true,
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
