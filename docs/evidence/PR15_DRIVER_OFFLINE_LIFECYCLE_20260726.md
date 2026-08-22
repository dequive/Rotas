# PR-15 — Lifecycle offline do Driver

Data: 2026-07-26  
Estado: `done_local`  
Escopo validado: persistência local, retry/dead-letter, recuperação de sessão,
cold start com snapshot e reconciliação sem duplicação observável

## Alterações

- Dexie evoluiu para a versão 3 sem remover stores existentes.
- `syncQueue` e `photoQueue` guardam `lastAttemptAt`, `nextAttemptAt` e
  `deadLetteredAt`.
- retries usam backoff exponencial persistente, jitter e limite de cinco
  tentativas.
- a quinta falha transitória passa explicitamente para `dead_letter`; não fica
  invisivelmente parada como `retrying`.
- itens deixados em `syncing` por encerramento abrupto regressam a `retrying`
  no arranque seguinte.
- conflitos, falhas terminais e dead-letter podem ser reenfileirados
  explicitamente; um payload corrigido recebe uma nova `Idempotency-Key`.
- a sincronização renova o access token uma vez após 401 e reutiliza o token
  rodado no restante lote.
- sessão expirada não consome tentativas; acesso revogado preserva os dados e
  produz falha terminal visível.
- o bootstrap online é guardado com chave `tenantId:driverId`; cold start
  offline só aceita snapshot da mesma identidade.
- sem snapshot válido, acções que exigem uma viagem activa permanecem
  bloqueadas.
- ao recuperar rede, a fila é processada imediatamente e depois verificada a
  cada 30 segundos; apenas itens cujo `nextAttemptAt` venceu chegam à rede.
- um painel local lista `conflict`, `failed` e `dead_letter`; reenfileirar gera
  nova chave e descartar exige confirmação, removendo operação, fotografias e
  registo de combustível na mesma transação Dexie.

## Evidência local

```text
Driver typecheck: 0 erros
Driver Vitest: 4 ficheiros, 23 testes, 23 passed
Driver Vite/PWA build após a UI: 1.807 módulos
Service worker injectManifest: 93 módulos
Precache: 6 entradas, 348,04 KiB
```

Os testes provam:

- backoff persistente e bloqueio antes de `nextAttemptAt`;
- recuperação de item interrompido;
- transição para dead-letter na quinta falha;
- requeue com payload e chave novos;
- conflito terminal;
- refresh 401 com rotação e reutilização do token;
- expiração sem consumo de tentativas;
- cache bootstrap estritamente limitado ao mesmo tenant/motorista.
- requeue e descarte transacional através do painel de recuperação.

## Ensaio Chromium e descoberta

Foi criado um E2E Playwright que abre o PWA online, confirma a gravação do
snapshot no IndexedDB, fecha a página e reabre o mesmo contexto totalmente
offline. A primeira execução removeu uma asserção transitória. A segunda
execução mostrou que o Workbox `api-cache` ainda servia o bootstrap autenticado
offline, contornando o snapshot Dexie scoped.

Foi então adicionada uma rota `NetworkOnly` prioritária para
`/api/v1/driver/bootstrap`. Assim, o bootstrap offline só pode vir do Dexie
validado por tenant e motorista.

A recompilação final e o ensaio Chromium passaram:

```text
Playwright Chromium: 1 teste, 1 passed em 17,3 s
```

O percurso comprovou:

1. bootstrap online e snapshot tenant/driver-scoped no IndexedDB;
2. encerramento da página e novo arranque completamente offline;
3. viagem activa recuperada do snapshot e aviso de modo offline;
4. ausência do bootstrap autenticado no `api-cache` do Workbox;
5. criação de operação offline com chave de idempotência;
6. recuperação de rede e uma única chamada de sync, com a mesma chave no
   cabeçalho e no corpo;
7. remoção da operação reconciliada da fila local;
8. segundo sinal de rede sem nova chamada, isto é, sem duplicação observável.

## Limites de certificação e próximos gates

- o backend de bootstrap/sync foi simulado no E2E; staging, dispositivo
  instalado e rede móvel real continuam por certificar;
- o service worker permaneceu activo para navegação e cold start, mas a
  resposta de sync foi simulada no `window.fetch`, porque o routing Playwright
  não intercepta o `fetch` iniciado pelo service worker; o replay real do
  Workbox Background Sync sob falha de rede permanece no PR-22;
- rede degradada, concorrência e relógio divergente permanecem no PR-22;
- isolamento e purge completo de caches no logout/troca de identidade
  permanecem no PR-16.

Esta evidência fecha os critérios de engenharia local do PR-15. Não certifica
staging, dispositivo físico nem o release candidate.
