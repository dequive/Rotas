---
plan: 08-07
phase: 08-infrastructure-hardening
status: complete
completed_at: 2026-06-07
self_check: PASSED
---

## What Was Built

Sentry frontend integration for Next.js manager and Vite driver PWA — DSN-guarded, silent in local dev (INFRA-01).

## Key Files Created

- `apps/manager/instrumentation.ts` — `register()` with `NEXT_PUBLIC_SENTRY_DSN` guard, initialises Sentry only on Node.js runtime
- `apps/driver/src/sentry.ts` — `Sentry.init()` guarded by `VITE_SENTRY_DSN_DRIVER`, side-effect import pattern

## Key Files Modified

- `apps/manager/package.json` — `@sentry/nextjs: ^8`
- `apps/manager/next.config.mjs` — `withSentryConfig` wrapper, `experimental.instrumentationHook: true`, source map upload conditional on `SENTRY_AUTH_TOKEN`
- `apps/driver/package.json` — `@sentry/browser: ^8`, `@sentry/vite-plugin: ^2` (devDep)
- `apps/driver/vite.config.mjs` — `sentryVitePlugin` conditional on `SENTRY_AUTH_TOKEN`, `build.sourcemap: true`
- `apps/driver/src/main.tsx` — `import "./sentry"` as first import

## Verification

TypeScript: both apps `tsc --noEmit` clean (exit 0).

## Commits

- `49e85cd` — feat(08-07): add @sentry/nextjs to manager
- `d454835` — feat(08-07): add @sentry/browser + vite-plugin to driver PWA
