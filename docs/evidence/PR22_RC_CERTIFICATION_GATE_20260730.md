# PR-22 — Gate do Bundle de Certificação RC

Data: 2026-07-30  
Estado: `implemented_local_not_executed_in_rc`  
Gate afectado: G4 — continua vermelho

## Resultado

Foi removida a possibilidade de uma execução isolada com perfil
`staging_certification` parecer uma aprovação de release. O relatório individual
é agora classificado como:

```text
release_evidence_fragment
```

Somente o contexto completo validado por
`scripts.performance_certification` pode constituir
`release_evidence_context`.

## Bundle obrigatório

O contexto exige:

- SHA Git completo de 40 caracteres;
- backend publicado por `RepoDigest`, sem tag mutável;
- API e métricas em HTTPS não-local;
- runner externo e não co-localizado com a API;
- papel operacional PostgreSQL exactamente `rotas_app`;
- `pg_stat_statements` activo;
- dois UUIDs de tenant distintos;
- tokens efémeros apenas em `ROTAS_PERF_TENANT_A_TOKEN` e
  `ROTAS_PERF_TENANT_B_TOKEN`;
- quatro cenários canónicos para cada tenant;
- soak declarado e observado de pelo menos 7.200 segundos.

São necessários oito fragmentos:

| Tenant | Cenários |
| --- | --- |
| tenant_a | api_read, offline_sync_batch, idempotency_race, degraded_network |
| tenant_b | api_read, offline_sync_batch, idempotency_race, degraded_network |

Cada fragmento deve:

- usar o perfil `staging_certification`;
- conter o mesmo `ROTAS_RELEASE_SHA` integral do contexto;
- estar `passed=true`;
- ter todos os checks internos explicitamente `true`;
- corresponder ao tenant e base URL do contexto;
- manter `authorization=redacted`;
- atingir o volume mínimo do cenário;
- conter scrapes de pool;
- conter amostras de event-loop e CPU.

O próprio gerador rejeita staging sem SHA integral, volume mínimo, API HTTPS
externa ou endpoint HTTPS externo de métricas.

## SQL seguro

`scripts.export_pg_stat_statements` lê a URL administrativa exclusivamente de
`ROTAS_PERF_ADMIN_DATABASE_URL`. O artefacto contém apenas:

- query ID;
- calls;
- tempo total e médio;
- rows;
- shared block hits/reads;
- temporary blocks written.

Texto SQL, parâmetros e identificadores de negócio nunca são exportados. O
validador rejeita qualquer campo adicional.

## Soak

O relatório de soak deve corresponder ao SHA do contexto e declarar:

```text
duration_seconds >= 7200
observability_window_complete = true
unresolved_sev1_sev2 = 0
completed = true
```

## Validação local

```text
Pytest focado:                  21 passed
Ruff:                           green
Pyright:                        0 erros, 0 warnings
Validador PR-22:                green
Controlos de certificação:      4
Artefactos de certificação:     2
Fragmentos exigidos no bundle:  8
```

O template deliberadamente não executável está em
`infra/performance/PR22_CERTIFICATION_CONTEXT.example.json`.

## Limite

Isto prova o gate e as rejeições, não os resultados do RC. Não existem ainda
RepoDigest publicado, oito fragmentos reais, export real de
`pg_stat_statements`, dois tenants autorizados ou soak concluído. PR-22 continua
`in_progress` e G4 continua vermelho.
