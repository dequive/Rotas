# PR09 — Contrato OpenAPI e cliente Manager gerado

Data: 2026-08-08

Branch: `codex/pr09-openapi-client`

Base: `acc41b1` (`codex/pr08-manager-bff-boundary`)

## Resultado

Estado: **done_local para os critérios próprios do PR09**; **não certificado para release**.

O FastAPI passa a ser a fonte canónica de um contrato OpenAPI 3.1 versionado e
determinístico. O Manager gera tipos TypeScript desse contrato e instancia um
cliente `openapi-fetch` cujo transporte remapeia todas as operações para o BFF
same-origin.

```text
backend/openapi/rotas-v1.json
SHA-256: 544e0f6e77bff96fa705fe859cb9c639ce0d640d2cdbd3c0aa6821b08ad2d112
297 paths
364 operações
207 schemas
```

## Contrato backend

`backend/scripts/export_openapi.py`:

- serializa JSON com chaves ordenadas e newline determinístico;
- exige OpenAPI 3.x e pelo menos um path;
- exige `operationId` presente e único em todas as operações;
- em `--check`, falha quando o ficheiro versionado não existe ou diverge da app.

O CI executa o check depois de Ruff e Pyright e antes das migrations/testes.

## Tipos e cliente Manager

`openapi-typescript 7.13.0` gera:

```text
apps/manager/app/generated/rotas-api.ts
```

`check:api-types` usa `--check` e bloqueia drift JSON→TypeScript. O cliente
`generated-api-client.ts`:

- expõe paths, parâmetros, corpos e respostas tipados;
- remove `Authorization` mesmo quando um consumidor browser tenta fornecê-lo;
- encaminha pathname, query, método, headers e body pelo `bffRequest`;
- mantém os tokens de sessão exclusivamente no servidor BFF.

A migração dos helpers de domínio para o cliente gerado pertence ao PR10 e não
foi antecipada neste PR.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| `export_openapi.py --check` | verde; hash confirmado |
| Testes backend do contrato/drift | 3 passed |
| Ruff focado | verde |
| Pyright integral | 0 erros, 0 warnings |
| `check:api-types` | verde |
| Teste do cliente gerado | 1 passed |
| Partição BFF + cliente | 12 passed em 3 ficheiros |
| Gate AST BFF | 98 raízes, 120 módulos browser, 0 violações |
| `git diff --check` | verde |

## Validação ampla e bloqueios herdados

A suíte Manager coletou 75 testes aprovados. `WorkOrderDetail.test.tsx` continua
sem coletar porque o ramo empilhado ainda não contém a implementação PR03/Oficina
presente apenas no working tree principal. Um timeout de `AcceptQuoteModal` na
execução concorrente passou no rerun focado (1/1) e não foi reproduzido como
defeito PR09.

O typecheck mantém exatamente os seis diagnósticos herdados do PR08/base:
três referências da OS detalhada, um parâmetro implícito em Analytics e duas
incompatibilidades de `SheetContentProps`. O cliente gerado não acrescentou
diagnósticos.

A instalação npm offline não pôde reconstruir toda a árvore porque o tarball
`@redocly/openapi-core` não estava no cache. Geração e check foram executados
com `openapi-typescript 7.13.0` já instalado no workspace; `npm ci` e os checks
reproduzíveis ainda dependem da CI/RC com acesso normal ao registry.

## Decisão de gate

- Critério PR09 (contrato versionado, tipos gerados e drift blocking): **verde local**.
- G2 global: **yellow**.
- Merge/promoção: **NO-GO** até integrar PR03, executar `npm ci`, suíte/typecheck/build
  integrais no SHA candidato, CI remota, revisão independente e reprodução no RC.
