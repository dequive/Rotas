# PR-23 — Gate de Certificação de Segurança e Privacidade

Data da evidência: 2026-07-31  
Estado: `implemented_local_not_executed`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementado o agregador fail-closed dos três controlos PR-23 exigidos
pelo decisor G4: `pentest_independent`, `zero_high_critical` e
`privacy_approved`. O contrato está verde localmente, mas o template devolve
deliberadamente `NO-GO`; nenhum pentest ou parecer jurídico foi alegado.

O modelo `PR23-THREAT-MODEL-V1` permanece uma baseline de engenharia com as 16
ameaças abertas. O resultado deste gate é um `release_evidence_fragment`
separado e não altera retroactivamente a baseline.

## Contrato exigido

### Pentest independente

- autorização/RoE e canal cifrado;
- assessor externo sem conflito;
- quatro RepoDigests e SHA do RC;
- nove papéis, incluindo dois tenants com IDs sobrepostos e `rotas_app`;
- doze superfícies de edge, auth, BFF, API, control plane, Driver, RLS,
  storage, domínios ERP, outbox/Governance, BI e abuso;
- contas/allowlists removidas e auditoria reconciliada.

### Findings e reteste

- zero high/critical abertos;
- todos os findings remediados retestados pelo assessor independente;
- zero retestes falhados e zero release blockers;
- as 16 ameaças baseline exercitadas;
- medium/low com ID único, owner e prazo futuro.

### Privacidade

- parecer jurídico independente e válido para Moçambique;
- matriz controller/processor e papéis contratuais dos tenants;
- finalidade/base legal, retenção, DSAR, excepções imutáveis e offboarding;
- subprocessadores, transferências/residência, breach response e dados
  restritos;
- oito fluxos de privacidade testados e zero riscos high abertos;
- governance explícita para BI cross-tenant.

## Evidência física

São exigidos nove JSON com `kind`, SHA integral do release e SHA-256:
autorização, pentest, cobertura, findings, reteste, matriz, parecer,
subprocessadores e testes de lifecycle.

## Artefactos

- `backend/scripts/security_certification.py`
- `backend/tests/test_security_certification.py`
- `infra/security/PR23_SECURITY_CERTIFICATION_CONTEXT.example.json`
- `docs/security/PR23_PENTEST_RULES_OF_ENGAGEMENT.md`
- `.github/workflows/ci.yml`

## Validação local

```text
Pytest do novo gate:         5 passed
Ruff:                        green
Pyright:                     0 errors, 0 warnings
Template JSON:               válido
Template execution:          NO-GO esperado
Pentest/parecer RC:          não executados
```

## Bloqueadores mantidos

- PR-18 continua com vulnerabilidades high;
- PR-19 ainda não produziu staging/RepoDigests reais;
- Rules of Engagement permanece sem aprovação;
- não existe assessor contratado, pentest ou reteste;
- matriz jurídica e parecer de privacidade não foram aprovados;
- threat model continua com 16 release blockers abertos.

Conclusão: o contrato de certificação está implementado, mas PR-23 permanece
`in_progress` e G4 permanece vermelho.
