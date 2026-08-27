# PR-23 — Baseline de Threat Model, Privacidade e Pentest

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations

## Resultado

Foi criada uma baseline multi-tenant versionada e validada automaticamente:

- hierarquia fixa `ROTAS SaaS -> tenant independente -> clientes do tenant`;
- 12 trust boundaries e 10 activos;
- 16 ameaças STRIDE com owner, controlo, evidência, risco residual e prova
  requerida;
- quatro classes de dados e oito fluxos de privacidade;
- política fail-closed de G4, sem aceitação de high/critical;
- escopo e Rules of Engagement mínimos para pentest independente;
- validador e oito testes negativos/positivos integráveis no CI.

Artefactos:

- `infra/security/ROTAS_SECURITY_MODEL.json`;
- `docs/security/ROTAS_THREAT_AND_PRIVACY_MODEL.md`;
- `docs/security/PR23_PENTEST_RULES_OF_ENGAGEMENT.md`;
- `backend/scripts/validate_security_model.py`;
- `backend/tests/test_security_model.py`.

## Evidência local

```text
Validador: status ok
Threats: 16
Open release blockers: 16
Privacy classes: 4
Privacy flows: 8
Pytest: 8 passed
Ruff: All checks passed
```

Os testes provam que o gate rejeita alteração da hierarquia SaaS, score
incoerente, remoção de boundary/fluxo, pré-fecho de risco, alegação de pentest
executado e padrões de segredo.

## Riscos abertos

- PR-18: 4 vulnerabilidades high em produção e 17 high no grafo completo;
- PR-19: não existe RC implantado em staging;
- acesso support ainda não tem concessão JIT/break-glass completa;
- ficheiros não têm prova de bucket policy/scanning real;
- privacidade/retention/DSAR/offboarding carecem de política, jornadas e
  validação jurídica;
- observabilidade real ainda não tem canary de fuga de dados;
- PR-22 não passou budgets de latência/soak;
- pentest independente está `not_executed`.

Logo, esta baseline não certifica segurança, privacidade ou conformidade legal.
PR-23 avança de `pending` para `in_progress`; G4 permanece vermelho e o estado
global permanece `NO-GO`.

