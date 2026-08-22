# PR-19 — Gate de Certificação Runtime do Staging

Data da evidência: 2026-07-31  
Estado: `implemented_local_not_executed`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementado o agregador fail-closed para os quatro controlos PR-19
exigidos pelo decisor G4: `immutable_images`, `tls`, `external_secrets` e
`migrations`. O contrato e os testes estão verdes localmente, mas o template
devolve deliberadamente `NO-GO`; nenhum staging remoto foi certificado.

O resultado é um `release_evidence_fragment`. Só pode alimentar PR-19 quando
`passed=true`, os quatro controlos estão verdes, os nove ficheiros físicos têm
hash válido e SRE/TL aprovam o mesmo SHA do release.

## Evidência exigida

- `supply_chain_result`: resultado físico PASS do gate das quatro imagens, 20
  provas e SHA coincidente;
- quatro `tls_probe`: Manager, Driver, API e Grafana com HTTPS, cadeia e
  hostname verificados, TLS 1.2/1.3, validade residual mínima de 30 dias e HSTS
  de pelo menos um ano com `includeSubDomains`;
- `secret_manager_report`: os 18 secrets externos, injectados por ficheiro,
  ausentes do ambiente runtime/repositório e material temporário removido;
- `migration:rotas` e `migration:governance`: execução one-shot, exit code
  zero, heads observadas e timestamps; ROTAS exige ainda `alembic check` limpo;
- `runtime_report`: `/version`, `/health/deep`, heartbeat do worker, aplicações
  iniciadas depois das migrations e ligação PostgreSQL como `rotas_app`,
  NOSUPERUSER e sem BYPASSRLS.

Todas as provas precisam de SHA-256, SHA integral do release, operador e
recolha por runner externo.

## Artefactos

- `backend/scripts/staging_certification.py`
- `backend/tests/test_staging_certification.py`
- `infra/staging/PR19_STAGING_CERTIFICATION_CONTEXT.example.json`
- `docs/STAGING_DEPLOYMENT_RUNBOOK.md`
- `.github/workflows/ci.yml`

## Validação local

```text
Pytest do novo gate:         4 passed
Ruff:                        green
Pyright:                     0 errors, 0 warnings
Template JSON:               válido
Template execution:          NO-GO esperado
Staging/RC externo:          não executado
```

## Bloqueadores mantidos

- não existe SHA de RC nem provider/registry/staging definidos;
- faltam assinatura/attestations/scanner/admission reais;
- não existem certificados, probes TLS/HSTS nem DNS reais;
- secret manager e 18 secrets não foram materializados remotamente;
- migrations e aplicação não foram executadas num staging remoto;
- papel efectivo `rotas_app`, saúde profunda e heartbeat não foram observados;
- PR-18 continua com vulnerabilidades high.

Conclusão: o caminho de prova PR-19 está completo no plano local, mas PR-19
permanece `in_progress` e G4 permanece vermelho até à execução no RC.
