# PR-24 — Gate de Certificação de Acessibilidade e Jornadas

Data: 2026-07-31  
Estado: `in_progress`  
Decisão actual: `NO-GO`

## Resultado

Foi implementado o agregador fail-closed do PR-24. O contrato local consegue
validar um bundle completo, mas o template canónico permanece deliberadamente
vermelho: nenhuma evidência externa foi fabricada e G4 não foi promovido.

## Controlos

O fragmento de release expõe exactamente os controlos esperados pelo decisor
G4:

- `wcag_2_2_aa`;
- `manual_assistive`;
- `mobile_real`;
- `role_coverage`.

O gate exige o mesmo SHA integral e os quatro RepoDigests imutáveis do RC,
runner externo e 11 artefactos JSON físicos com SHA-256. Evidência alterada,
duplicada, incompleta ou pertencente a outro release invalida o controlo.

## Escopo obrigatório

- inventário integral das rotas Manager/Driver, builds verdes e zero critério
  A/AA falhado, teste ignorado ou excepção aberta;
- auditor independente e matriz completa NVDA/Firefox, JAWS/Chrome,
  VoiceOver/Safari e TalkBack/Chrome;
- teclado, foco, modais, zoom 200%, reflow 400%, forced colors, orientação,
  target size, autenticação/erros e actualizações dinâmicas;
- dispositivos físicos Android e iOS, retrato/paisagem, gestos de leitor de
  ecrã, touch e jornada Driver com uma mão;
- sete papéis, nove jornadas principais, todos os estados, utilizadores reais,
  dois tenants com identificadores sobrepostos e zero fuga cross-tenant.

## Artefactos

- `backend/scripts/accessibility_certification.py`;
- `backend/tests/test_accessibility_certification.py`;
- `infra/accessibility/PR24_ACCESSIBILITY_CERTIFICATION_CONTEXT.example.json`.

## Validação local

```text
Pytest PR-24: 5 passed
Ruff: green
Pyright focado: 0 errors, 0 warnings
JSON template: válido
Template executado: exit code 1, decisão NO-GO, quatro controlos false
git diff --check focado: green
```

## Critério de promoção

PR-24 só pode ficar verde quando o agregador for executado contra o RC real e
devolver `PASS`, e os sign-offs FE-M, FE-D e PO forem ligados ao SHA e ao digest
das evidências no manifesto G4. A baseline automatizada de 2026-07-28 continua
útil, mas não substitui auditoria manual, dispositivos reais ou aceitação.
