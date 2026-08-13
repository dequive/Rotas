# Issue #25 — External Certification Runbook

Status: **prepared / NO-GO until executed**
Scope: PR #41 and one exact release-candidate SHA
Owners: SRE (CI/Sentry), QA + FE-D (Android), SEC (privacy review), TL (final decision)

## Purpose

This runbook closes only the three external gates that cannot be certified by local mocks or emulators: remote GitHub CI, runtime Sentry delivery and a physical low-end Android journey. It does not change billing and must never target the online database.

The validator is fail-closed. `GO` requires all three sections for the same full Git SHA. Missing, partial, simulated or stale evidence returns `NO_GO`; malformed or secret-bearing evidence returns `INVALID`.

## Safety contract

- Copy `infra/release/ISSUE25_EXTERNAL_CERTIFICATION.template.json` to a temporary or approved evidence location. Do not overwrite the template.
- The untouched template is intentionally `INVALID` (`run_id: 0`) so it can never be promoted by changing only pass booleans. Replace every placeholder with observed evidence.
- Never put DSNs, auth tokens, passwords, tenant IDs, user/driver IDs, emails, raw event payloads or device owner data in the JSON.
- The schema is an allowlist. Unknown keys and common secret-bearing keys are rejected.
- URLs must point to access-controlled HTTPS dashboards/runbooks/artifacts; they are references, not embedded evidence.
- Do not run migrations, seeds or destructive commands against the online database.

## Gate A — Remote CI

Prerequisite: the GitHub account billing lock has been resolved.

1. Rerun the CI workflow for the exact candidate SHA; do not create an empty commit merely to retrigger it.
2. Confirm `Backend`, `Frontend` and `E2E` all conclude `success`.
3. For each job, record its positive `runner_id` and the number of executed steps. `runner_id=0` or `steps_executed=0` is an automatic `NO_GO`.
4. Record the workflow `run_id`, `head_sha` and conclusion. The `head_sha` must equal `commit_sha`.
5. If GitHub again annotates a billing/account/runner refusal, stop; do not weaken the workflow, remove services, skip tests or use `continue-on-error`.

Rollback: none. A failed certification changes no runtime state. Keep PR #41 draft and Issue #25 open.

## Gate B — Sentry staging

Prerequisites: approved non-production Manager and Driver Sentry projects, runtime DSNs configured through the secret channel, and an alert notification destination.

1. Deploy/build the exact candidate SHA in `staging`; keep `sendDefaultPii=false`.
2. Exercise Manager Web Vitals and Driver bootstrap/sync success and controlled-failure paths.
3. Inspect actual events/spans and confirm they contain only the allowlisted attributes documented in `docs/UX_TELEMETRY_SLOS.md`; SEC must confirm no identity, tenant, token, payload or raw entity route leakage.
4. Create the seven dashboards/alerts named in the template, using the thresholds and minimum volumes from `docs/UX_TELEMETRY_SLOS.md`.
5. Test-fire every alert and prove delivery to the intended destination. Every alert must link to an HTTPS runbook.
6. Record only booleans and evidence URLs in the JSON. Never record DSNs or tokens.

Rollback: remove the staging DSNs/disable telemetry initialization and alerts. Telemetry failure must remain non-blocking for application journeys.

## Gate C — Physical low-end Android

Prerequisites: a physical Android device with 512–4096 MB RAM, ADB available to QA, and a controlled unstable-network profile. Emulator evidence is useful for development but cannot certify this gate.

1. Install the Driver build from the exact candidate SHA on the physical device.
2. Enable reduced-motion at OS level and prove bootstrap, navigation and sync remain functional.
3. Execute the offline lifecycle: disconnect, create/queue the supported operation, restart the PWA, reconnect under unstable network and prove eventual single synchronization without duplicate effects.
4. Confirm the fixed sync region remains readable and does not create perceptible layout shift during offline/syncing/error/success changes.
5. Capture an access-controlled video/test report without notifications, accounts, personal data or tenant/customer content visible.
6. Record device class, RAM, network profile, three pass booleans and the HTTPS artifact URL. Do not record serial number, IMEI, account or owner identity.

Rollback: uninstall the candidate build and reinstall the last certified Driver version; preserve the failed evidence for diagnosis.

## Validate and decide

From `backend`:

```powershell
.\.venv\Scripts\python.exe scripts\validate_issue25_external_gates.py `
  --evidence <approved-evidence.json> `
  --expected-sha <40-character-candidate-sha>
```

Exit code `0` and `decision: GO` are necessary but not sufficient for merge: TL and SEC must review the linked evidence, PR approvals and all repository release gates. Any other result keeps Issue #25 open, PR #41 draft and Issue #26 blocked.
