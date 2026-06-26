# ROTAS — Shipped Milestones

## v1.0 MVP
- **Shipped**: 2026-06-06
- **Summary**: Initial operational MVP for fleets.
- **Key accomplishments**:
  - Security hardening (PyJWT, rate limiting, secure cookies).
  - PWA offline-first driver application with background sync.
  - Basic manager dashboard with telemetry reporting.
  - Automated maintenance scheduler.

## v2.0 Plataforma Operacional Completa
- **Shipped**: 2026-06-26
- **Summary**: Full client registry, payments, accounts receivable, and driver settlement platform with row-level security and customer tracking.
- **Key accomplishments**:
  - **Database Row-Level Security (RLS)**: Enforced multi-tenant isolation at the database level on 47+ tables with a dedicated test suite.
  - **Driver Financial Settlement (Despacho)**: Added trip-linked cash advances, expense deduction, manager approval, and PDF settlement sheets.
  - **Client Registry & Payments**: Migrated flat client names to a first-class `clients` table, added payment recording and aging accounts receivable.
  - **GPS Integration & Customer Tracking**: Live vehicle tracking map for managers and unauthenticated public `/track/[token]` link for customers with auto-refresh and staleness indicators.
  - **Onboarding & Notifications**: Self-service signup with atomic transactions, SMTP Portuguese fallbacks, and a Meta WhatsApp templates outbox queue.
