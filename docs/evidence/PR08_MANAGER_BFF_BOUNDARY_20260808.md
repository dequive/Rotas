# PR08 — Manager Browser/BFF Boundary

Data: 2026-08-08

Branch: `codex/pr08-manager-bff-boundary`

Base: `7b6773d` (`codex/pr07-platform-entitlements`)

## Resultado

Estado: **done_local para os critérios próprios do PR08**; **não certificado para release**.

- O browser do Manager comunica apenas com rotas same-origin em `/api/**`.
- Tokens de acesso e `Authorization` ficam fora do grafo alcançável pelo browser.
- Endereços do backend usam somente `ROTAS_API_BASE_URL` no servidor.
- O proxy genérico falha fechado sem sessão, rejeita destinos externos/path traversal,
  preserva query, `Idempotency-Key` e `X-Request-Id`, roda uma vez o token após 401,
  devolve 502 tipado e bloqueia mutações cross-origin.
- O backend de billing e as suas regras de negócio não foram alterados. Os componentes
  browser de billing passaram a chamar as rotas BFF existentes ou o proxy same-origin.

## Gate bloqueante

O gate AST parte de todos os módulos com `"use client"`, percorre imports locais
estáticos e dinâmicos, termina em módulos `"use server"` e rejeita:

- `localStorage` e `sessionStorage` no grafo browser;
- tokens `access_token`/`refresh_token` e cabeçalhos `Authorization` no browser;
- variáveis públicas com endereço do backend;
- `fetch` direto a `/api/v1` ou a URL absoluta;
- destinos dinâmicos não demonstráveis;
- `XMLHttpRequest`, `WebSocket` e `EventSource` fora da fronteira aprovada.

Resultado:

```text
Manager BFF boundary verified: 97 client roots, 119 browser-reachable modules, 0 violations.
```

O CI executa `test:bff-boundary` e `verify:bff` antes da suíte Manager.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| Testes Node do gate AST | 7 passed |
| Testes Vitest BFF/proxy | 11 passed em 2 ficheiros |
| Inventário AST | 97 raízes, 119 módulos browser, 0 violações |
| `git diff --check` | verde |
| Suíte Manager no PR08 | 74 passed; 1 suite herdada não coletada |
| Suíte Manager no base `7b6773d` | 63 passed; a mesma suite herdada não coletada |
| TypeScript no PR08 | mesmos 6 diagnósticos do base; zero erro novo |

## Bloqueios herdados e ambiente

O ramo empilhado ainda não contém a implementação PR03/Oficina presente apenas no
working tree principal. Por isso `WorkOrderDetail.test.tsx` referencia
`WorkOrderDetailClient` e tipos de `workshop-api` que não existem no base deste PR.
O typecheck confirma ainda duas falhas herdadas de `components/ui/sheet.tsx`.
Estas mesmas falhas foram reproduzidas num worktree limpo de `7b6773d`; não foram
mascaradas nem corrigidas fora de sequência no PR08.

O build Turbopack no worktree temporário foi bloqueado porque a junção local de
`node_modules` aponta para fora da raiz do projeto. A tentativa Webpack ultrapassou
essa validação de symlink, mas excedeu o limite local de 180 segundos. O build
reproduzível permanece dependente da integração/publicação do PR03 e de CI/RC limpos.

## Decisão de gate

- Critério PR08 (zero token em storage e chamadas diretas = 0): **verde local**.
- G2 global: **yellow**.
- Merge/promoção: **NO-GO** até integrar PR03 no ramo candidato, obter suíte e build
  integrais verdes, executar CI remota, revisão independente e reprodução no RC.
