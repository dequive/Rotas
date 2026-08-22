# ADR-009: Governação canónica de agentes e convergência

## Status

Accepted

## Date

2026-08-22

## Context

O ROTAS acumulou planos, logs, matrizes, evidências e mais de vinte PRs abertos
ou empilhados. Agentes diferentes passaram a usar snapshots distintos como
fonte de verdade. A auditoria da branch da Issue #42 encontrou uma base local
forte, mas também regressões do Driver, fronteiras de autorização incompletas,
gates locais vermelhos e trabalho Android aprovado existente apenas numa linha
Git divergente.

O resultado foi um sistema em que uma afirmação podia ser verdadeira numa
branch e falsa noutra: por exemplo, “Driver mostra viagens atribuídas” e
“Actions estão fixadas por SHA”. Essa ambiguidade é incompatível com um ERP/TMS
SaaS enterprise e impede revisão, certificação e rollback confiáveis.

## Decision

1. `AGENTS.md` passa a ser o ponto de entrada vinculativo para todos os agentes.
2. A hierarquia documental definida em `AGENTS.md` é obrigatória. Evidência e
   histórico nunca promovem estado por si próprios.
3. `docs/PRODUCTION_RELEASE_LEDGER.md` é a única autoridade para GO/NO-GO.
4. `docs/CURRENT_STATE_AND_CONVERGENCE_PLAN_20260822.md` é a baseline auditada
   da convergência Issue #42 e permanece válida até ser substituída por nova
   auditoria no SHA integrado.
5. Segurança e convergência Driver/Sync precedem Issue #43 e qualquer nova
   expansão funcional.
6. Convergência entre branches será feita por fatias contratuais testáveis, não
   por merge/cherry-pick indiscriminado.
7. Quando documentos divergirem, prevalece o gate mais restritivo até uma
   atualização explícita e verificável corrigir todas as fontes canónicas.

## Alternatives Considered

### Manter cada plano ou relatório autónomo

Rejeitado porque perpetua regras concorrentes e permite que um agente escolha
o snapshot que confirma a sua implementação.

### Usar apenas o corpo do PR mais recente

Rejeitado porque o PR #44 já ficou desatualizado em relação ao próprio HEAD e
um corpo de PR não é ledger operacional nem contrato de produto.

### Fazer merge integral da linha Android na branch atual

Rejeitado porque as duas linhas partem do mesmo merge-base e alteram muitas das
mesmas superfícies. Um merge integral mistura soluções alternativas, migrations
e testes e torna a revisão impraticável.

## Consequences

- Agentes têm uma ordem única de leitura e não podem inventar sequências.
- PR #44 e Issue #42 permanecem abertos até os bloqueios documentados fecharem.
- O trabalho pode avançar mais devagar no curto prazo, mas cada incremento será
  revisável, reproduzível e reversível.
- Toda promoção de estado exige atualização coordenada do plano, matriz e
  ledger no mesmo SHA.
- Snapshots antigos continuam no histórico, mas ficam explicitamente
  não vinculativos.

## Supersession

Esta decisão não substitui ADRs de arquitetura funcional. Ela governa a
precedência entre documentos e o método de convergência. Uma decisão futura
que a altere deve criar novo ADR e referenciar explicitamente `ADR-009`.
