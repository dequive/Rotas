# PR-21 — Gate de Certificação de Disaster Recovery

Data da evidência: 2026-07-31  
Estado: `implemented_local_not_executed`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementado o agregador fail-closed dos quatro controlos PR-21 exigidos
pelo decisor G4: `backup_restore`, `pitr`, `cross_region` e `rpo_rto`.
O contrato está verde localmente, mas o template devolve deliberadamente
`NO-GO`; nenhum DR remoto foi certificado.

O output é um `release_evidence_fragment`. Só pode alimentar PR-21 quando
`passed=true`, os quatro controlos estão verdes e os onze relatórios JSON
físicos estão vinculados ao mesmo SHA.

## Contrato exigido

### Backup e restore

- staging, volume representativo e autorização explícita dos dados;
- restic cifrado client-side, `check --read-data`, manifesto/checksum e remoção
  do plaintext temporário;
- restore isolado com Alembic limpo;
- todas as tabelas tenant com FORCE RLS;
- zero diários desequilibrados;
- jornadas de autenticação, RLS multi-tenant, Oficina, faturação e outbox;
- Governance e dados/configuração da observabilidade recuperados;
- cleanup confirmado.

### PITR

- WAL contínuo sem erros;
- restore point criado e atingido;
- timeline e restore PITR verificados;
- perda medida entre zero e 900 segundos.

### Cross-region

- regiões e failure domains distintos;
- réplica cifrada, versionada e com object lock mínimo de 30 dias;
- lag entre zero e 900 segundos;
- credenciais separadas;
- indisponibilidade primária simulada e restore efectuado pela réplica.

### RPO/RTO

- RPO medido até 15 minutos;
- RTO medido entre zero e 240 minutos;
- duração reconciliada com timestamps;
- carga/volume representativos;
- operador de restore diferente do operador de backup;
- paging do incidente exercitado.

## Artefactos

- `backend/scripts/dr_certification.py`
- `backend/tests/test_dr_certification.py`
- `infra/dr/PR21_DR_CERTIFICATION_CONTEXT.example.json`
- `docs/DR_BACKUP_RESTORE_RUNBOOK.md`
- `.github/workflows/ci.yml`

## Validação local

```text
Pytest do novo gate:         5 passed
Ruff:                        green
Pyright:                     0 errors, 0 warnings
Template JSON:               válido
Template execution:          NO-GO esperado
DR staging/RC:               não executado
```

## Bloqueadores mantidos

- não existe PITR/WAL real nem medição RPO;
- não existe storage object-locked e cross-region;
- restore remoto com volume representativo não foi executado;
- Governance e observabilidade não foram recuperados;
- não houve perda simulada de região, operador independente ou paging real;
- RPO/RTO ainda não foram aprovados por SRE/QA.

Conclusão: o contrato de certificação está implementado, mas PR-21 permanece
`in_progress` e G4 permanece vermelho.
