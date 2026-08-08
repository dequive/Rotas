# PR07 - Entitlements controlados pela plataforma

Data: 2026-08-08

Baseline: `896a1575350a67ffdfa460b6a23dfa55163234ce` (PR06)

Branch: `codex/pr07-platform-entitlements`

## Resultado

PR-07 está `done_local`. Um tenant já não consegue conceder a si próprio
módulos comerciais durante o onboarding, pelo PATCH genérico de configurações
ou pelo endpoint legado `/tenants/me/modules`.

A operação canónica é agora:

`PATCH /api/v1/platform/tenants/{tenant_id}/product-modules`

Ela exige identidade `platform_admin`, usa a sessão administrativa introduzida
no PR06, valida os módulos contra o catálogo executável do runtime, invalida a
cache do tenant e grava `tenant.product_modules_changed` em
`platform_audit_logs` na mesma transação da mutação.

## Contratos exercidos

- onboarding público atribui apenas o baseline `tms`;
- `product_modules` enviado no onboarding público é rejeitado com 422;
- `product_modules` enviado em `PATCH /tenants/me` é rejeitado com 422;
- o endpoint legado do tenant devolve 403 `entitlement_managed_by_platform`;
- `platform_support` e `platform_billing` não podem alterar módulos;
- `platform_admin` pode conceder módulos válidos;
- módulos vazios ou desconhecidos são rejeitados sem mutação nem audit falso;
- concessões válidas guardam actor, papel, tenant alvo e valores anterior/novo;
- fixtures de Oficina provisionam entitlements fora da API tenant-facing.

## Evidência local

```text
testes focados PR07 + fixtures migradas: 24 passed
regressão backend repetida: 551 passed, 1 skipped, 1 warning
Ruff app + tests: PASS
compileall app + tests: PASS
Pyright global: 0 errors, 0 warnings
Pyright escopo PR07: 0 errors, 0 warnings
git diff --check: PASS
```

A primeira regressão completa terminou com 550 passados e uma falha do teste de
rate limiting. O teste passou 2/2 isoladamente e a repetição integral passou
551/551; a ocorrência foi tratada como instabilidade dependente da ordem e não
como evidência omitida.

## Limites e gate

- nenhum ficheiro em `backend/app/modules/billing` foi alterado;
- o billing comercial da plataforma não foi redesenhado neste PR;
- `done_local` não significa certificação de release;
- G2 permanece amarelo até PR08-PR10, revisão independente, merge da pilha,
  CI remota e reprodução em release candidate.
