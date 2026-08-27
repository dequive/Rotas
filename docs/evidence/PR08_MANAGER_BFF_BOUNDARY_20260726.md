# PR-08 — Manager BFF-only e Tokens HttpOnly

Data: 2026-07-26  
Estado: `done_local`

## Resultado

O inventário AST do Manager analisou 94 módulos com directiva `"use client"` e
encontrou zero violações da fronteira Browser → BFF → API.

O gate bloqueia:

- `localStorage` e `sessionStorage` em módulos autenticados client-side;
- `access_token` e `refresh_token` no código do browser;
- construção de cabeçalho `Authorization` no browser;
- `fetch` absoluto ou dirigido diretamente a `/api/v1`;
- `NEXT_PUBLIC_API_URL`, `ROTAS_API_BASE_URL` e
  `VITE_ROTAS_API_BASE_URL` em módulos client-side;
- import do helper server-side `lib/api`;
- `XMLHttpRequest`, `WebSocket` e `EventSource` como bypass da fronteira.

Chamadas server-side em Server Components e Route Handlers são permitidas e
continuam a obter os tokens exclusivamente de cookies no servidor.

## Evidência automatizada

```text
Manager BFF boundary verified: 94 client modules, 0 violations.

node:test:
4 passed

Vitest:
14 test files passed
75 tests passed

TypeScript:
tsc --noEmit passou

Next.js:
build de produção passou
72 páginas geradas
```

O teste runtime `auth-bff.test.ts` confirma que o login:

- guarda access e refresh token em cookies `HttpOnly`, `SameSite=Lax`;
- não devolve os tokens no corpo da resposta ao browser.

O workflow de CI executa o inventário, os testes do próprio gate, toda a suite
Vitest, typecheck e build.

## Limites

Esta evidência é local e baseada no working tree. PR-08 só poderá ser
considerado certificado depois de reprodução no SHA do release candidate pela
CI remota. O gate estático não substitui E2E de segurança nem pentest; esses
critérios permanecem em G2/PR-23.
