# ROTAS — Runbook de Backup, Restore e DR

## Estatuto

Este runbook implementa a baseline PR-21. O drill local prova o percurso
técnico, mas não certifica RPO/RTO, storage cross-region ou recuperação de
staging/produção.

Política canónica: `infra/dr/DR_POLICY.json`.

## Objectivos propostos

- PostgreSQL RPO: até 15 minutos;
- PostgreSQL RTO: até 4 horas;
- dump lógico cifrado: pelo menos diário;
- PITR/WAL: contínuo ou frequência equivalente ao RPO;
- restore independente: mensal;
- cópia cifrada, imutável e noutro failure domain/região.

Os valores só ficam aprovados depois de Produto, SRE e QA assinarem evidência
medida em staging com volume representativo.

## Secrets

O URL PostgreSQL deve existir num ficheiro de valor único e usar
`rotas_admin` ou `rotas_owner`. O directório restic deve conter:

- `restic_repository`: endpoint `s3:https://...` sem credenciais inline;
- `restic_password`: pelo menos 32 caracteres;
- `aws_access_key_id`;
- `aws_secret_access_key`.

O bucket deve aplicar TLS, versionamento, object lock mínimo de 30 dias,
retenção e réplica cross-region. Credenciais de restore devem estar separadas
das credenciais normais da aplicação.

## Backup lógico cifrado

O scratch deve ser um volume cifrado ou filesystem em memória. O script nunca
recebe passwords na linha de comandos, gera dump custom, manifesto SHA-256,
revision Alembic e arquiva ambos num repositório restic cifrado.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.dr_backup `
  --database-url-file C:\secure\rotas-admin-url `
  --restic-secrets-dir C:\secure\restic `
  --scratch-root R:\encrypted-scratch `
  --report-path ..\docs\evidence\pr21-backup-<timestamp>.json `
  --release-sha <sha-integral> `
  --postgres-bin "C:\Program Files\PostgreSQL\16\bin" `
  --confirm-anonymized `
  --confirm-encrypted-scratch `
  --read-data
```

`--initialize-repository` só é usado na criação controlada do repositório.
Inicialização concorrente ou automática em cada backup é proibida.

## Restore isolado

O alvo deve ser novo e obedecer ao prefixo `rotas_dr_`. O script recusa
overwrite, valida checksum/tamanho, revision Alembic, mínimo de tabelas,
FORCE RLS e equilíbrio dos diários.

```powershell
.\.venv\Scripts\python.exe -m scripts.dr_restore `
  --database-url-file C:\secure\rotas-admin-url `
  --restic-secrets-dir C:\secure\restic `
  --scratch-root R:\encrypted-scratch `
  --report-path ..\docs\evidence\pr21-restore-<timestamp>.json `
  --snapshot-id <snapshot-id> `
  --target-database rotas_dr_monthly_202607 `
  --postgres-bin "C:\Program Files\PostgreSQL\16\bin" `
  --confirm-disposable-target
```

O operador independente deve ainda executar migrations/check, jornadas de
autenticação, RLS multi-tenant, Oficina, faturação, outbox e reconciliação.
Somente depois pode remover o alvo com `dropdb`.

## Retenção

Preview é o default e nunca elimina snapshots:

```powershell
.\.venv\Scripts\python.exe -m scripts.dr_retention `
  --restic-secrets-dir C:\secure\restic `
  --report-path ..\docs\evidence\pr21-retention-preview.json
```

Execução exige confirmação literal e corre `restic check` após prune:

```powershell
.\.venv\Scripts\python.exe -m scripts.dr_retention `
  --restic-secrets-dir C:\secure\restic `
  --report-path ..\docs\evidence\pr21-retention-execution.json `
  --execute `
  --confirm-policy PR21-RETENTION-V1
```

## Gate DR

PR-21 só pode ser concluído quando:

1. PITR/WAL demonstra RPO de 15 minutos;
2. backup real cifrado existe em região/failure domain independente;
3. object lock e retenção são verificados;
4. restore integral cumpre RTO de 4 horas sob volume real;
5. checksums, Alembic, RLS, contabilidade e jornadas passam;
6. Prometheus/Grafana e respectivos dados/configuração são recuperados;
7. perda do host/região é simulada sem reutilizar credenciais comprometidas;
8. operador independente e owners assinam o relatório;
9. alerta, escalonamento e comunicação do incidente são exercitados.

## Bundle de certificação PR-21

Copiar `infra/dr/PR21_DR_CERTIFICATION_CONTEXT.example.json` para o directório
seguro do RC. O template é deliberadamente NO-GO e não aceita resultados do
drill local como substituto da execução staging.

O bundle exige onze relatórios JSON físicos:

- backup, restore, invariantes e recuperação da observabilidade;
- PITR e arquivo WAL;
- storage primário, réplica e object lock;
- medição RPO/RTO e relatório do operador independente.

Cada JSON precisa de `kind`, SHA integral do release e SHA-256 no contexto. O
restore deve usar operador diferente do operador do backup, volume
representativo autorizado e runner externo. Devem ser recuperados ROTAS,
Governance e observabilidade, com FORCE RLS integral, diários equilibrados e
as cinco jornadas canónicas.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.dr_certification `
  --context C:\secure\PR21_DR_CERTIFICATION_CONTEXT.json `
  --output C:\secure\PR21_DR_CERTIFICATION_RESULT.json
```

O resultado é somente um `release_evidence_fragment`. Só alimenta
`backup_restore`, `pitr`, `cross_region` e `rpo_rto` quando `passed=true`, os
quatro controlos estão verdes e SRE/QA aprovam os hashes.
