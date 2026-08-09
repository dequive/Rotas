---
phase: quick-260810-0fe
status: completed
date: 2026-08-10
issue: https://github.com/dequive/Rotas/issues/34
---

# Resumo: GitHub Actions fixadas por SHA

## Resultado

- O unico workflow rastreado continha oito referencias a quatro Actions oficiais.
- `actions/checkout@v4` foi resolvida para
  `11d5960a326750d5838078e36cf38b85af677262`.
- `actions/setup-python@v5` foi resolvida para
  `a26af69be951a213d495a4c3e4e4022e16d87065`.
- `actions/setup-node@v4` foi resolvida para
  `49933ea5288caeca8642d1e84afbd3f7d6820020`.
- `actions/upload-artifact@v4` foi resolvida para
  `ea165f8d65b6e75b540449e92b4886f43607fa02`.
- Um gate fail-closed bloqueia tags, branches, SHAs curtos e owners fora de
  `actions`/`dequive`.
- Dependabot ficou configurado para actualizacoes semanais de `github-actions` por PR.

## Evidencia local

- `test_validate_action_pins.py`: 5 testes passaram.
- `validate_action_pins.py`: 8 referencias fixadas e validas.
- Ruff: verde.
- YAML: 2 ficheiros validos.
- `git diff --check`: verde.

## Limite

Esta entrega remove o bloqueio de politica de supply chain identificado na CI. O billing
do GitHub Actions continua separado na Issue #33; nenhum resultado remoto e declarado
verde ate os jobs iniciarem e concluirem no SHA desta mudanca.
