# Phase 8: Infrastructure Hardening — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-06
**Phase:** 08-infrastructure-hardening
**Areas discussed:** Limit Banner UX, R2 Migration Safety, Sentry Project Structure

---

## Limit Banner UX

| Option | Description | Selected |
|--------|-------------|----------|
| Top de todas as páginas | Banner persistente no topo do layout principal quando qualquer limite ≥ 80% | ✓ |
| Inline na secção relevante | Aviso só na página de Frota/Motoristas relevante | |

**User's choice:** Top de todas as páginas
**Notes:** Banner persistente, visível em todo o dashboard.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Não dismissível | Persiste até upgrade ou utilização baixar | ✓ |
| Dismissível até próxima sessão | Gestor pode fechar; reaparece no próximo login | |

**User's choice:** Não dismissível

---

| Option | Description | Selected |
|--------|-------------|----------|
| null = ilimitado | Enterprise plan sem limite; guards fazem skip | ✓ |
| null = usa o default | Herda defaults 5/5/3 do modelo | |

**User's choice:** null = ilimitado (plano enterprise)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Variável de ambiente UPGRADE_URL | Configurável sem re-deploy | ✓ |
| URL hardcoded por ambiente | Menos env vars mas inflexível | |

**User's choice:** UPGRADE_URL env var

---

## R2 Migration Safety

| Option | Description | Selected |
|--------|-------------|----------|
| Script Python one-shot via CLI | backend/scripts/migrate_files_to_r2.py; app continua online | ✓ |
| Endpoint admin | POST /api/v1/admin/migrate-files-to-r2 | |

**User's choice:** Script Python CLI
**Notes:** App continua online durante a migração.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Skip e continua, log o erro | Lista falhas no final; exit code 1 se houver falhas | ✓ |
| Abort na primeira falha | Mais seguro mas pode deixar estado inconsistente | |

**User's choice:** Skip e continua, log o erro

---

## Sentry Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Um projecto Sentry, três DSNs | SENTRY_DSN_BACKEND + SENTRY_DSN_MANAGER + SENTRY_DSN_DRIVER | ✓ |
| Três projectos Sentry separados | Isolamento total mas mais overhead | |

**User's choice:** Um projecto, três DSNs

---

| Option | Description | Selected |
|--------|-------------|----------|
| Sentry desactivado em dev | DSN ausente = silencioso | ✓ |
| Sentry activo em dev | Captura erros de dev; polui o painel | |

**User's choice:** Desactivado em dev

---

## Claude's Discretion

- Design visual exacto do LimitWarningBanner (seguir DESIGN.md tokens)
- Estratégia de cache Redis (hash vs múltiplas chaves)
- Formato do log de progresso do script de migração

## Deferred Ideas

- Dashboard de utilização histórica por tenant
- Alertas automáticos de limite via WhatsApp/email (Phase 10)
