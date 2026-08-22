# PR-25 — Gate de Certificação de Incidentes e Game Day

Data: 2026-07-31  
Estado: `in_progress`  
Decisão actual: `NO-GO`

## Resultado

Foi implementado o agregador fail-closed do PR-25. O tabletop local continua
sem efeito no gate; o novo contrato só aceita execução humana e production-like
contra os mesmos SHA e RepoDigests do RC.

## Dependências obrigatórias

O gate rejeita PR-25 se os fragmentos PR-20, PR-21, PR-22 e PR-23 não tiverem
`PASS`, hash físico válido e o mesmo `release_sha`. Isto impede certificar
incidentes antes de observabilidade, DR, performance e segurança.

## Controlos

- `paging`: roster externo, primário/secundário, entrega e ack humanos dos cinco
  alertas canónicos por fornecedor real;
- `escalation`: SEV1–SEV4, incident commander, escalonamento secundário,
  comunicação tenant-scoped e zero violação dos SLAs;
- `game_day`: cinco cenários, falha real, contenção/recuperação medidas,
  validação independente, RPO <= 15 min e RTO <= 240 min;
- `signoff`: presença dos seis papéis, postmortem, todas as acções encerradas,
  acessos temporários removidos e aprovação SRE/PO/QA.

São exigidos dez artefactos JSON físicos com SHA-256, runner externo, quatro
RepoDigests imutáveis e zero drift de escopo ou release.

## Artefactos

- `backend/scripts/incident_certification.py`;
- `backend/tests/test_incident_certification.py`;
- `infra/operations/PR25_INCIDENT_CERTIFICATION_CONTEXT.example.json`.

## Validação local

```text
Pytest PR-25 baseline + certificação + release gate: 12 passed
Ruff: green
Pyright focado: 0 errors, 0 warnings
JSON template: válido
Template executado: exit code 1, decisão NO-GO, quatro controlos false
git diff --check focado: green
```

## Critério de promoção

PR-25 só fica verde quando o agregador devolver `PASS` no RC e os sign-offs SRE
e PO forem ligados ao SHA e ao digest do workstream no manifesto G4. O template
permanece deliberadamente `NO-GO`; nenhuma pessoa, paging, falha ou recuperação
foi simulada como evidência real.
