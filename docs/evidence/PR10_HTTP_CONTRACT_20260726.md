# PR-10 — Contrato HTTP comum (incremento 1)

Data: 2026-07-26  
Estado: `done_local`  
Escopo validado: clientes Manager/Driver, sincronização offline e BFF upstream

## Resultado

Foi criado o workspace package `@rotas/http-contract`, sem dependência de
React ou Next, para concentrar:

- timeout por `AbortController`, com código tipado `request_timeout`;
- envelope `HttpContractError` com `status`, `code`, `message`, `details` e
  `retryable`;
- parsing uniforme do envelope de erro ROTAS;
- retry com backoff exponencial, jitter e `Retry-After`;
- retry automático apenas para métodos seguros ou mutações com
  `Idempotency-Key`;
- geração/preservação de chave de idempotência.

O contrato foi integrado em:

- `apps/manager/app/lib/bff.ts`;
- `apps/manager/app/lib/api.ts`;
- `apps/driver/src/api.ts`;
- `apps/driver/src/sync.ts`.

No segundo incremento, `apps/manager/app/lib/upstream-http.ts` tornou-se a
fronteira única BFF -> API. Todos os 36 route handlers são inventariados por
AST; 49 chamadas upstream diretas em 35 handlers foram migradas e o gate rejeita qualquer
nova chamada `fetch` dentro de `app/api/**/route.ts`.

Esta fronteira:

- propaga `Idempotency-Key` e `X-Request-Id` recebidos;
- não cria retry para mutações que chegaram sem chave;
- devolve `504 request_timeout` em timeout;
- preserva o contrato público `502 upstream_unavailable` para falha de rede;
- não expõe exceções ou detalhes internos do transporte.

No Driver:

- mutações online recebem automaticamente uma chave estável;
- retry transitório reutiliza a mesma chave;
- `sync/batch` envia a chave persistida tanto no envelope como no cabeçalho;
- upload de fotografia tem timeout de 30 segundos, mas zero retry automático,
  porque ainda não existe prova de idempotência desse upload;
- refresh de token também não repete automaticamente, evitando rotação
  ambígua quando a resposta se perde.

## Evidência local

```text
npm run typecheck
  Manager: 0 erros
  Driver: 0 erros
  @rotas/http-contract: 0 erros

Manager Vitest
  17 files passed
  85 tests passed

Driver Vitest
  3 files passed
  14 tests passed

Manager production build
  compilado; 72 páginas geradas

Driver production build (fora da sandbox OneDrive)
  1.806 módulos; PWA injectManifest; precache 6 entradas
```

Os contract tests provam leitura com retry/`Retry-After`, mutação sem chave sem
retry, mutação idempotente com chave preservada, timeout tipado, envelope de
erro e atribuição automática da chave no BFF. Os testes Driver provam a mesma
chave em duas tentativas e o erro estruturado.

O gate BFF analisou 98 módulos client-side e 36 route handlers, com zero
violações. Os seus 6 testes positivos/negativos também passaram.

## Limite de certificação

PR-10 está `done_local`: o contrato e o comportamento estão uniformizados e
protegidos contra regressão no repositório. Isto ainda não certifica rede
degradada real, compatibilidade de todos os proxies num release candidate ou
execução em staging.

Esta evidência é de engenharia local numa working tree. Não substitui CI
remota no SHA do release candidate, testes de rede degradada nem certificação
em staging.
