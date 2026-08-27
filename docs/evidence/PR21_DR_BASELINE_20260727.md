# PR-21 — Baseline de Backup, Restore e DR

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementado e exercitado localmente um percurso cifrado:

```text
PostgreSQL -> pg_dump custom -> manifesto SHA-256 -> restic cifrado
-> restic check --read-data -> restore isolado -> invariantes -> cleanup
```

Restic 0.18.1 foi fixado pelo digest
`sha256:39d9072fb5651c80d75c7a811612eb60b4c06b32ffe87c2e9f3c7222e1797e76`.

## Drill local

Fonte: base local de desenvolvimento confirmada como não-produção. Não foi
declarada anonimizada e nenhum artefacto foi enviado para fora da máquina.

| Medida | Resultado |
| --- | ---: |
| Revision | `rec13` |
| Dump | 29.817.862 bytes |
| SHA-256 | `e13f0a361ce4ffdb29938c3e692ccf2579c8eda3295aa58211596add76edf09a` |
| Tempo de dump | 28,648 s |
| Snapshot restic | `7076b6d1c9d9e21edfac5d5d2fb8349df0a34273462e179bb1aa3e429862549a` |
| `restic check --read-data` | verde em 5,020 s |
| Restore PostgreSQL | 58,338 s |
| Tabelas públicas | 123 |
| Tabelas FORCE RLS | 113 |
| Diários desequilibrados | 0 |
| Base descartável removida | sim |
| Plaintext temporário removido | sim |

O preview da retenção `PR21-RETENTION-V1` manteve o snapshot e não eliminou
dados. Execução real de prune exige confirmação literal separada.

Artefactos:

- `PR21_LOCAL_BACKUP_20260727.json`;
- `PR21_LOCAL_RESTORE_20260727.json`;
- `infra/dr/DR_POLICY.json`;
- `docs/DR_BACKUP_RESTORE_RUNBOOK.md`.

## Controlos implementados

- URL PostgreSQL apenas em ficheiro, sem password nos argumentos;
- produção aceita somente `rotas_admin` ou `rotas_owner` e exige TLS;
- scratch de produção exige confirmação de volume cifrado/memory-backed;
- repositório restic cifra client-side e usa imagem imutável;
- dump e manifesto são arquivados juntos;
- checksum, tamanho, revision e release SHA são fail-closed;
- restore recusa overwrite e só aceita alvo `rotas_dr_*`;
- verificação de tabelas, FORCE RLS e equilíbrio contabilístico;
- política RPO 15 min/RTO 4 h, object lock 30 dias e cópia cross-region;
- retenção preview por default; prune exige `PR21-RETENTION-V1`;
- target e plaintext temporário foram removidos depois do sucesso.

## Gates locais

```text
Pytest DR:                 12 passed
Ruff:                      green
Pyright:                   0 erros, 0 warnings
Validador DR:              RPO=15, RTO=240, 5 níveis de retenção
Dump/restic/read-data:     green
Restore/invariantes:       green
Retenção dry-run:          green
```

## Limitações

- o scratch local não era cifrado/memory-backed; foi aceite apenas por
  `--local-drill` e removido;
- não foi usado snapshot real anonimizado de staging/produção;
- não existe ainda PITR/WAL para provar RPO de 15 minutos;
- o repositório era local, não object-locked, cross-region ou independente;
- o volume e a carga não são representativos;
- o RTO local de 58,338 s não aprova RTO de produção;
- PostgreSQL Governance e volumes Prometheus/Grafana ainda não foram
  recuperados;
- não houve operador independente, falha de região, on-call ou game day.

Assim, PR-21 avança para `in_progress`, mas G4 permanece vermelho.
