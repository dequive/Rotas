# PR-16 — Isolamento de cache por identidade do Driver

Data: 2026-07-26  
Estado: `done_local`  
Escopo validado: tenant, motorista, sessão, logout, troca de identidade e purge

## Fronteira implementada

- cada operação de sync, fotografia, registo de combustível e snapshot de
  bootstrap guarda `tenantId`, `driverId` e `sessionId`;
- o IndexedDB evoluiu para Dexie v4 com índices compostos de identidade;
- snapshots usam a chave `tenantId:driverId:sessionId`;
- sincronizador, recuperação de itens interrompidos, upload de evidências,
  contadores e painel de conflitos só consultam a identidade corrente;
- operações antigas ou de outra identidade não chegam à rede;
- cada novo emparelhamento recebe um `sessionId` aleatório;
- logout invalida primeiro access token, refresh token e identidade local;
- a rotação de token em curso não pode restaurar credenciais depois do logout;
- todas as tabelas operacionais Dexie são limpas numa transação;
- `api-cache`, cache de sync e fila Workbox são drenados;
- assets públicos content-hashed permanecem disponíveis;
- falha ou timeout do purge bloqueia novo emparelhamento e oferece retry.

O POST de sync usa agora `NetworkOnly` com fallback Background Sync. Uma
mutação nunca é armazenada como entrada de Cache Storage.

## Evidência automatizada

```text
Driver Vitest: 5 ficheiros, 26 testes, 26 passed
Driver typecheck: 0 erros
Driver build: 1.808 módulos
Service worker: 93 módulos
Precache: 6 entradas, 351,39 KiB
Playwright Chromium: 2 testes, 2 passed em 18,1 s
```

Os testes unitários provam:

- snapshot de outra sessão do mesmo tenant/motorista não é recuperado;
- fila de outra identidade não é enviada;
- logout apaga credenciais, todas as tabelas Dexie e caches autenticados;
- `static-assets` não é apagado.

O ensaio Chromium provou:

1. sessão antiga carregada e cache autenticado preenchido;
2. logout com confirmação de todas as tabelas IndexedDB a zero;
3. access token, refresh token, tenant e sessão removidos;
4. `api-cache` eliminado;
5. novo emparelhamento só disponível após o purge;
6. novo tenant/motorista recebe uma sessão diferente;
7. o E2E anterior de cold start offline e reconciliação continua verde.

## Limites de certificação

- pairing e bootstrap foram simulados no browser; o backend real não fez parte
  deste ensaio;
- falta repetir em staging e dispositivo Android instalado, incluindo crash,
  storage pressure e interrupção durante o purge;
- a evidência pertence ao working tree, não a um SHA de release candidate;
- pentest, observabilidade e rede degradada permanecem nos gates PR-20,
  PR-22 e PR-23.

Esta evidência fecha os critérios de engenharia local do PR-16. Não promove o
release global, que permanece `NO-GO`.
