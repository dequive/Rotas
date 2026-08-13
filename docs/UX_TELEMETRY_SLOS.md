# ROTAS UX Telemetry SLOs

Status: instrumentation implemented locally; dashboards and runtime alerts are not certified.

## Privacy and tenancy contract

- Telemetry is disabled when the corresponding Sentry DSN is absent.
- `sendDefaultPii` is explicitly disabled in Manager client and Driver initialization.
- Custom UX spans contain only `app`, `metric`, `rating`, `operation`, `outcome`, numeric value and unit.
- Tenant IDs, user/driver IDs, emails, tokens, payloads, full URLs and entity routes are prohibited by a tested allowlist.
- Aggregation is release/application-wide. It must not be used to compare named tenants or individuals.
- Telemetry failures are contained and never block login, bootstrap, sync or offline operations.

## Initial service levels

| Signal | Target | Alert threshold | Window / minimum volume |
|---|---:|---:|---|
| Manager CLS | p75 <= 0.10 | p75 > 0.10 | 30 min / 100 samples |
| Manager LCP | p75 <= 2500 ms | p75 > 2500 ms | 30 min / 100 samples |
| Manager INP | p75 <= 200 ms | p75 > 200 ms | 30 min / 100 samples |
| Driver bootstrap | p95 <= 3000 ms | p95 > 5000 ms | 30 min / 50 samples |
| Driver sync | p95 <= 5000 ms | p95 > 10000 ms | 30 min / 50 samples |
| Driver bootstrap unavailable | < 2% | >= 5% | 30 min / 50 samples |
| Driver sync error | < 2% | >= 5% | 30 min / 50 samples |

## Release gate

1. Configure `NEXT_PUBLIC_SENTRY_DSN_MANAGER` and `VITE_SENTRY_DSN_DRIVER` through the approved secret/configuration channel.
2. Verify spans in a non-production environment without identity or tenant attributes.
3. Create dashboards grouped only by release, environment, app, metric/operation and outcome/rating.
4. Apply the alert thresholds above and prove notification delivery.
5. Observe at least one release window before using the signals as a production gate.

Until all five steps have runtime evidence, Wave 3 remains NO-GO for release certification.
