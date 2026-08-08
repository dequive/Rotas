# PR10 — Contrato HTTP comum, retries e idempotência

Data: 2026-08-09

Branch: `codex/pr10-http-contract`

Base: `0b2037e` (`codex/pr09-openapi-client`)

## Resultado

Estado: **done_local para os critérios próprios do PR10**; **não certificado para release**.

O pacote interno `@rotas/http-contract` centraliza timeout, erros tipados,
retry com backoff exponencial e jitter, `Retry-After` e idempotência. Uma
mutação só pode ser repetida quando possui `Idempotency-Key`; métodos seguros
podem repetir falhas transitórias sem essa chave.

## Integrações

- Manager browser: `bffRequest` mantém o caminho same-origin, acrescenta uma
  chave estável às mutações e preserva o envelope ROTAS em erros tipados.
- Manager server: `apiFetch` utiliza a política comum e preserva a mesma chave
  numa repetição e após refresh de token.
- Manager BFF: `upstreamFetch` é a única fronteira de transporte para os 33
  handlers que contactam a API; encaminha apenas `Idempotency-Key` e
  `X-Request-Id` e converte timeout/rede para respostas 504/502 saneadas.
- Driver: API e sync usam o contrato comum; o lote offline envia a chave
  persistida tanto no envelope como no header. Upload de fotografia possui
  timeout de 30 segundos e zero retries automáticos, evitando replay de
  `FormData`.

Não foram introduzidas as rotas de ficheiros, identidade offline, dead-letter,
backoff persistido ou outras entregas dos PRs posteriores. Billing permaneceu
funcionalmente congelado; a única alteração sob a sua rota foi a substituição
mecânica do transporte BFF pela fronteira comum.

## Gate BFF reforçado

O gate AST do PR08/09 continua a seguir imports estáticos e dinâmicos a partir
de módulos `use client` e a respeitar `use server` como fronteira terminal. O
PR10 acrescenta a inspeção dos 34 route handlers e bloqueia qualquer chamada
direta a `fetch` dentro deles.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| Typecheck `@rotas/http-contract` | verde |
| Testes focados Manager | 16 passed em 3 ficheiros |
| Testes do gate BFF | 9 passed |
| Gate AST BFF | 98 raízes, 120 módulos browser, 34 handlers, 0 violações |
| Testes Driver integrais | 14 passed em 3 ficheiros |
| Typecheck Driver | verde |
| Pesquisa de `fetch` direto em handlers | 0 ocorrências; 33 handlers usam `upstreamFetch` |
| `git diff --check` | verde |

## Validação ampla e bloqueios herdados

A suíte Manager aprovou 81 testes. `WorkOrderDetail.test.tsx` continua sem
coletar porque o ramo empilhado não contém a implementação PR03/Oficina que
existe apenas no working tree principal. O typecheck mantém exatamente os seis
diagnósticos herdados: três referências da OS detalhada, um parâmetro implícito
em Analytics e duas incompatibilidades de `SheetContentProps`. O PR10 não
acrescentou diagnósticos.

O build Driver transformou 1.802 módulos da aplicação e 93 do service worker,
mas não conseguiu materializar `dist` por `EPERM` no worktree temporário. O
prebuild também encontrou `EPERM` ao tentar regravar `public/icon-192.png`.
São bloqueios de escrita do ambiente; typecheck e suíte integral Driver estão
verdes, mas o build deve ser repetido em CI/RC.

## Decisão de gate

- Critério PR10 (política comum, idempotência, BFF único e testes): **verde local**.
- G2 global: **yellow**.
- Merge/promoção: **NO-GO** até integrar a pilha, resolver os bloqueios
  herdados, executar `npm ci`, suites/typecheck/build integrais no SHA candidato,
  CI remota, revisão independente e reprodução no RC.
