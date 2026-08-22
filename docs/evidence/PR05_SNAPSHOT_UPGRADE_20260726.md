# PR-05 — Ensaio de Snapshot, Restore e Upgrade

Data: 2026-07-26  
Head validada: `rec11`  
PostgreSQL: 16.14, instância local `55432`

## Veredicto

O ensaio local sintético passou. Não constitui certificação de um snapshot real
de staging ou produção.

- snapshot de origem: base criada de `template0` e migrada até
  `95929ae669b9`;
- dados: tenant, utilizador, viatura, motorista, contrato, viagem, fornecedor,
  fatura, pagamento e diário contabilístico equilibrado;
- destino: restore isolado e upgrade `95929ae669b9 -> rec11`;
- resultado: `alembic current=rec11`, `alembic check` sem drift e 23 testes
  pós-upgrade verdes;
- risco: foram observados `AccessExclusiveLock` concedidos em muitas tabelas.
  O ensaio não autoriza upgrade online sob carga.

## Artefactos e tempos

| Medida | Resultado |
| --- | ---: |
| Migração vazia até `95929ae669b9` | 48,526 s |
| Dump custom | 1,499 s |
| Restore | 24,576 s |
| Tamanho do dump | 471.780 bytes |
| SHA-256 | `df45bc4ca396d59f4921e3f59496746141e4539feb911a1147f2f3ffa266d2b6` |
| Upgrade restaurado `95929ae669b9 -> rec11` | 12,487 s |
| Amostras de locks | 35, intervalo aproximado de 100 ms |
| Máximo de locks em espera observado | 0 |
| Forward-fix após preflight fail-closed | 14,097 s |

## Integridade após restore e upgrade

```text
tenants=1
trips=1
supplier_invoices=1
supplier_payments=1
linked_payments=1
journal_debit=1000.00
journal_credit=1000.00
```

Testes executados no restore migrado:

```text
test_payables_atomicity.py
test_composite_indexes.py
test_database_role_security.py
test_cross_tenant_isolation.py
test_rls.py
test_workshop_rls_multitenant.py

23 passed, 1 warning
```

O warning é o fallback local do rate limiter porque `REDIS_URL` foi
deliberadamente deixado vazio.

## Locks

O monitor amostrou `pg_locks` durante o upgrade. Não houve espera observada,
mas houve `AccessExclusiveLock` concedido em tabelas de faturação, viagens,
workshop, fornecedores, contabilidade, autenticação e outras tabelas
tenant-scoped. Também foram observados `ShareLock`, `AccessShareLock` e
`ExclusiveLock`.

Consequência operacional:

- executar em janela de manutenção até existir ensaio concorrente em staging;
- configurar `lock_timeout` e `statement_timeout` por migration runbook;
- acompanhar sessões bloqueadas e possuir critério de abort;
- medir novamente com volume e tráfego representativos.

## Ensaio de forward-fix

Foi restaurada outra cópia de `95929ae669b9` e introduzida deliberadamente uma
tabela `employees` parcial. O preflight de `4dd4802e1c18` abortou:

```text
Partial legacy HR/inventory snapshot; missing tables: ...
```

A revisão ficou em `92c11f6fdf9d`. Depois de remover somente o bloqueador
sintético conhecido, o upgrade terminou em `rec11` em 14,097 s e
`alembic check` passou.

Este ensaio prova a recuperação do bloqueio de preflight conhecido. Não prova
recuperação genérica de DDL parcialmente aplicado.

## Limitações e gate seguinte

PR-05 permanece `in_progress` até repetir com:

1. snapshot anonimizado de staging ou produção;
2. volume representativo;
3. tráfego concorrente controlado;
4. métricas de bloqueio e latência;
5. restore de rollback validado por operador independente.

As bases e ficheiros temporários sintéticos foram removidos após registar esta
evidência.

## Runbook automatizado

O procedimento foi automatizado em
`backend/scripts/pr05_snapshot_upgrade_gate.ps1`. O script:

- exige `-ConfirmAnonymized`;
- aceita apenas destinos com prefixo `rotas_pr05_`;
- recusa sobrescrever base, dump ou relatório;
- recebe passwords apenas por `PGPASSWORD` e
  `PR05_ALEMBIC_URL_TEMPLATE`;
- configura `lock_timeout` e `statement_timeout`;
- preserva base, dump e logs quando o gate falha;
- remove destino e dump somente após sucesso completo;
- gera relatório JSON com hash, tempos, locks e revisão.

O smoke endurecido está em `PR05_RUNBOOK_HARDENED_SMOKE_20260726.json`:
`rec11 (head)`, `alembic check` verde, 17 amostras de lock, zero erros do
monitor, `lock_timeout=5s`, `statement_timeout=15min` e cleanup automático
confirmado.

Exemplo, usando valores secretos fornecidos pelo ambiente:

```powershell
$env:PGPASSWORD = '<secret>'
$env:PR05_ALEMBIC_URL_TEMPLATE = `
  'postgresql+asyncpg://rotas_admin:<secret>@db.internal:5432/{database}'

.\backend\scripts\pr05_snapshot_upgrade_gate.ps1 `
  -SourceDatabase rotas_staging_anonymized `
  -TargetDatabase rotas_pr05_restore_candidate `
  -DumpPath C:\secure-temp\rotas-pr05.dump `
  -ReportPath .\docs\evidence\pr05-staging.json `
  -DatabaseHost db.internal `
  -ConfirmAnonymized
```
