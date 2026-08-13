# ROTAS Async UX and Motion Matrix

Status: Waves 1 through 3 implemented locally; authenticated Manager journeys are browser-proven against an ephemeral tenant database. Physical-device, telemetry-runtime and remote-CI certification remain pending.

## Contract

- Frequent, keyboard-driven interactions remain instant.
- Occasional transitions are interruptible and capped at 180 ms entering and 120 ms exiting.
- Motion uses opacity and transforms only; no layout property is animated.
- `prefers-reduced-motion: reduce` collapses non-essential animation and transitions globally.
- Loading, error, empty and stale states must remain informative without relying on motion.
- Billing behavior and the online database are outside this change.

## Matrix

| Surface | State/interaction | Policy | Owner | Risk | Wave |
|---|---|---|---|---|---|
| Manager global shell | Reduced motion | Collapse non-essential animation to 0.01 ms | Frontend Platform | Critical | 1 done |
| Driver PWA | Reduced motion / spinner | Stop continuous loops after one iteration | Driver/PWA | Critical | 2 browser-proven |
| Dialog / Sheet | Open and close | Transform + opacity, enter 180 ms, exit 120 ms | Design System | High | 1 done |
| Popover / Dropdown / Select | Open and close | Transform + opacity, enter 180 ms, exit 120 ms | Design System | High | 1 done |
| Skeleton / KPI loading | Pending | Pulse only when motion is allowed | Design System | High | 1 done |
| Vehicle and operational tabs | Keyboard/frequent switch | Instant; preserve focus and selection | Feature teams | Medium | 2 pending authenticated proof |
| Manager public auth | Slow network/error/focus | Stable error region, announced failure, keyboard order | Manager/Auth | High | 2 browser-proven |
| Manager vehicle mutation | Pending/success/error | Disabled pending action, real persisted success, announced error with preserved form context | Fleet | High | 2 authenticated browser-proven |
| Manager async panels | Loading/error/empty/stale | Stable reserved space; subtle optional enter only | Feature teams | High | 2 partial; vehicle mutation proven |
| Driver sync banner | Offline/syncing/blocked | Fixed 48 px region; persistent text/icon status | Driver/PWA | High | 2 browser-proven |
| Critical journeys | Slow network/retry/focus | Playwright journeys with reduced motion | QA | Critical | 2 partial: public auth, authenticated Manager mutation and Driver browser-proven |
| Runtime telemetry | Latency, errors, Web Vitals | Tenant-safe spans, no PII, explicit SLOs | Platform/SRE | Critical | 3 implemented locally; runtime pending |

## Release gates

1. Unit motion contracts, full frontend suites, typecheck and builds pass.
2. Browser journeys pass under reduced motion, keyboard navigation and slow network.
3. Low-end Android validation confirms usable Driver sync flows without layout shift.
4. Runtime telemetry and alert thresholds are approved without tenant or personal-data leakage.
5. Remote CI executes real jobs; startup failures or empty jobs are NO-GO.

## Authenticated Manager evidence

- The test runtime uses a disposable PostgreSQL 16 container on a dedicated local port; it does not use the online database.
- Alembic upgrades the disposable database to `head`, then `backend/tests/seed_e2e.py` creates a dedicated tenant and owner identity.
- `authenticated-async.spec.ts` delays the real vehicle POST to prove visible, disabled pending feedback and persists the result through Manager BFF, backend and PostgreSQL.
- The failure path injects an upstream 503 at the browser boundary and proves an announced error, preserved form values and an enabled retry action.
- Successful vehicle mutations revalidate the affected Manager routes so a completed operation cannot leave a stale list behind.
