# G4 — Gate Canónico de Decisão GO/NO-GO

Data: 2026-07-30  
Estado: `implemented_local_current_decision_no_go`  
Decisão actual: `NO-GO`

## Resultado

Foi criado um decisor único para G4. O manifesto apenas solicita `GO`; o script
`scripts.release_gate` decide com base em evidências PR-18 a PR-25.

O gate exige:

- SHA Git integral;
- exactamente oito workstreams;
- conjuntos de controlos canónicos, sem omissão ou campos improvisados;
- todos os controlos explicitamente `true`;
- pelo menos um artefacto por workstream;
- SHA-256 válido e correspondente ao conteúdo físico de cada artefacto;
- SHA do RC repetido em cada referência de artefacto;
- todos os papéis de sign-off obrigatórios;
- sign-off ligado ao digest conjunto das evidências do workstream;
- aprovadores distintos dentro do mesmo workstream.

## Cobertura

| Workstream | Fronteira bloqueante |
| --- | --- |
| PR-18 | dependências, zero high/critical não-waived, SBOM/attestation |
| PR-19 | imagens imutáveis, TLS, secrets, migrations |
| PR-20 | métricas, logs, traces, alertas, janela SLO |
| PR-21 | restore, PITR, cross-region, RPO/RTO |
| PR-22 | dois tenants, budgets, rede degradada, soak |
| PR-23 | pentest independente, findings, privacidade |
| PR-24 | WCAG, assistência manual, mobile, papéis |
| PR-25 | paging, escalonamento, game day, sign-off |

No total, o gate exige 17 sign-offs nominais distribuídos por SEC, TL, SRE, BE,
QA, FE-M, FE-D e PO.

## Rejeições provadas

Os testes confirmam `NO-GO` quando:

- um controlo permanece falso;
- um artefacto é alterado depois do hash;
- falta um papel de sign-off;
- falta qualquer workstream;
- o SHA não é integral;
- o manifesto actual ainda é apenas o template.

## Validação

```text
Pytest release gate: 3 passed
Ruff:                green
Template actual:     NO-GO esperado
```

## Limite

O gate não cria evidência nem substitui revisão independente. Ele impede que
evidência incompleta seja promovida por interpretação manual. Os artefactos
remotos e sign-offs reais ainda não existem; portanto G4 permanece vermelho,
PR-26 permanece bloqueado e a decisão global continua `NO-GO`.
