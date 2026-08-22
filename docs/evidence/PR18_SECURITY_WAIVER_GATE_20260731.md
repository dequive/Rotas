# PR-18 — Gate de Waiver Formal de Vulnerabilidades

Data: 2026-07-31  
Estado: `implemented_local`, nenhum waiver aprovado  
Gate afectado: G4 — permanece vermelho

## Motivo

O plano mestre exige zero vulnerabilidades high/critical, permitindo apenas
excepções formais com owner e prazo. O gate PR-18 V1 implementava somente o
caminho de zero findings e, por isso, não conseguia distinguir uma aceitação
formal de risco de uma omissão ou flag manual.

## Contrato V2

O relatório `PR18-DEPENDENCY-SECURITY-V2` enumera cada finding high/critical,
incluindo package, severity, range e referências directas do audit. Também
confirma que as contagens agregadas correspondem aos findings extraídos.

O caminho preferencial continua a ser zero findings. Um waiver opcional:

- fica dentro de `infra/release/waivers/` e ligado ao SHA integral do RC;
- cobre somente severity `high`; `critical` nunca é waivable;
- corresponde exactamente ao package e affected range observados;
- inclui todas as referências directas do advisory;
- possui justificação específica, owner e tracking URL HTTPS;
- possui pelo menos dois controlos compensatórios distintos;
- expira no máximo 30 dias depois da criação;
- possui aprovações distintas SEC e TL, ambas ligadas ao SHA;
- deixa de cobrir o finding quando é inválido, expirado ou incompleto.

Waivers adicionais que não correspondam ao audit actual também invalidam o
manifesto. Isso impede reutilizar uma aprovação antiga depois da mudança do
grafo.

## Template seguro

`infra/release/waivers/PR18_SECURITY_WAIVER.example.json` documenta o schema,
mas vem com `approved=false`, SHA fictício e placeholders. Não é evidência nem
aprovação.

## Prova local

O gate V2 foi executado sobre o grafo real com Node 20.20.2/npm 10.8.2, sem
manifesto de waiver:

```text
policy: PR18-DEPENDENCY-SECURITY-V2
gate exit: 1
production findings: 3
complete findings: 13
critical: 0
waiver provided: false
blockers:
  production_no_unwaived_high_critical
  complete_no_unwaived_high_critical
```

Portanto, implementar o mecanismo não alterou a decisão. PR-18 continua
`blocked_upstream`, G4 permanece vermelho e PR-26 continua bloqueado.

## Validação

```text
Pytest PR-18 + workflow + G4: 11 passed
Ruff: green
YAML parse: green
Node 20 gate real: NO-GO esperado
```

