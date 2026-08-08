# PR-05 — Endurecimento do gate de snapshot e upgrade

Data: 2026-08-08

Revisão de origem ensaiada: `95929ae669b9`

Head canónico validado: `rec13`

## Veredicto

O runbook endurecido passou com uma origem sintética e preservou o fingerprint
de integridade antes e depois do restore e upgrade. Este resultado valida a
mecânica local do gate, mas **não certifica PR-05**. O estado permanece
`in_progress` porque não foi disponibilizado um snapshot representativo,
anonimizado e formalmente autorizado de staging ou produção.

## Controlos acrescentados

- classe do snapshot obrigatória e limitada a `synthetic`,
  `staging_anonymized` ou `production_anonymized`;
- evidência externa de anonimização obrigatória, com origem, classe, revisor,
  instante e referência de aprovação consistentes;
- rejeição fail-closed de evidência com PII, sem aprovação ou incompleta;
- SQL de integridade obrigatório e comparação determinística do fingerprint;
- `DATABASE_URL` e `ALEMBIC_DATABASE_URL` fixados explicitamente ao destino
  restaurado durante o upgrade e repostos no final;
- hashes SHA-256 do dump, evidência de anonimização e SQL de integridade no
  relatório;
- template deliberadamente não aprovado, para não poder ser confundido com
  autorização real.

## Resultado do smoke sintético

O relatório estruturado está em
`docs/evidence/PR05_HARDENED_SYNTHETIC_SMOKE_20260808.json`.

| Medida | Resultado |
| --- | ---: |
| Dump | 470.585 bytes |
| SHA-256 do dump | `010043980bbb3e061efd336ee02374c2cb7569977554444903dc84a13c50bd3d` |
| Restore | 9,646 s |
| Upgrade `95929ae669b9 -> rec13` | 13,329 s |
| Amostras de locks | 34 |
| Máximo de locks em espera | 0 |
| Erros do monitor | 0 |
| `alembic check` | sem novas operações |

O fingerprint de integridade permaneceu igual:

```text
6db88e4df4381fe9ae8742924efb6ab0c3d350371eba5829d159b35d9647e5fe
```

Foram observados `AccessExclusiveLock`, `AccessShareLock`, `ExclusiveLock`,
`ShareLock` e `ShareUpdateExclusiveLock`. A ausência de espera nesta amostra
sintética não autoriza execução online sob carga.

## Execução do runbook

Além dos segredos fornecidos exclusivamente pelo ambiente, a execução real
deve informar os artefactos de prova obrigatórios:

```powershell
.\backend\scripts\pr05_snapshot_upgrade_gate.ps1 `
  -SourceDatabase rotas_staging_anonymized `
  -TargetDatabase rotas_pr05_restore_candidate `
  -SnapshotClass staging_anonymized `
  -AnonymizationEvidencePath .\secure\pr05-anonymization.json `
  -IntegritySqlPath .\infra\release\PR05_INTEGRITY.sql `
  -DumpPath C:\secure-temp\rotas-pr05.dump `
  -ReportPath .\docs\evidence\pr05-staging.json `
  -DatabaseHost db.internal `
  -ConfirmAnonymized
```

## Critérios ainda pendentes

PR-05 somente poderá fechar depois de existir evidência para todos estes
critérios:

1. snapshot anonimizado e aprovado de staging ou produção;
2. volume e distribuição de dados representativos;
3. tráfego concorrente controlado durante o upgrade;
4. métricas de bloqueio, latência e critério de abort;
5. validação funcional e contabilística após o upgrade;
6. restore/rollback executado por operador independente.

Até lá, a decisão de release continua `NO-GO`; esta entrega reduz risco e
torna o próximo ensaio auditável, mas não substitui a evidência operacional.

## Gates locais da alteração

```text
pytest tests/test_pr05_snapshot_gate.py: 2 passed
pytest backend completo: 532 passed, 1 skipped, 1 warning
Ruff (escopo CI): PASS
PowerShell parser: PASS
JSON parse: PASS
compileall com cache isolado: PASS
Pyright tests/test_pr05_snapshot_gate.py: 0 errors
```

O Pyright global, executado com o interpretador explicitamente resolvido,
reportou um único erro herdado em `app/modules/billing/service.py`: a variável
`existing_paid` pode não estar ligada. O PR-05 não altera billing e, por decisão
de escopo, não corrige nem oculta esse desvio. O gate global deve continuar
amarelo até o respetivo domínio ser autorizado para correção.

A primeira execução da suíte com `REDIS_URL` vazio falhou durante o import do
worker por DSN inválido. A repetição dos 34 testes afetados com
`redis://localhost:6381/0` passou, e a suíte integral com o mesmo ambiente
terminou verde. Esta ocorrência foi classificada como configuração incorreta
do ensaio, não como regressão do produto.
