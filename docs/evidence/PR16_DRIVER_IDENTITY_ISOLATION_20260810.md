# PR16 — Isolamento de identidade offline do Driver

Data: 2026-08-10

Branch: `codex/pr16-driver-identity`

Base: `41d2013` (`codex/pr15-driver-offline`)

## Resultado

Estado: **done_local para os critérios de engenharia do PR16**; **não
certificado para release**.

O armazenamento e o lifecycle offline do Driver passaram a ser isolados pela
identidade composta `tenantId + driverId + sessionId`:

- Dexie v4 adiciona o escopo composto às filas de sincronização, fotografias,
  combustíveis pendentes e snapshots de bootstrap;
- operações, evidências e snapshots novos recebem obrigatoriamente o escopo da
  sessão autenticada;
- registos v3 sem escopo ficam em quarentena: não são lidos, recuperados,
  apresentados, reenfileirados, descartados ou enviados sob uma sessão nova;
- sincronização, contadores e painel de incidentes filtram exclusivamente a
  identidade corrente;
- uploads e registos de combustível associados são reconciliados apenas quando
  pertencem à mesma identidade da operação;
- retry e descarte recusam acesso cruzado; o descarte filtra também as
  evidências por sessão, mesmo perante `localId` coincidente;
- cada pareamento cria um `sessionId` novo e sessões existentes recebem um
  identificador na primeira leitura sem promover dados legados.

## Logout e purge fail-closed

- as credenciais, incluindo refresh token e `sessionId`, são revogadas antes de
  qualquer limpeza assíncrona;
- uma geração de autenticação impede que um refresh iniciado pela sessão antiga
  restaure tokens depois do logout;
- o lock de refresh só pode ser libertado pela Promise que o adquiriu, evitando
  interferência com uma sessão posterior;
- o purge limpa todas as stores Dexie, `api-cache`, `sync-api` e a fila Workbox
  `rotas-sync-queue`;
- `static-assets` não é apagado, preservando a capacidade offline do PWA;
- a fila Workbox é agora explícita e drenável, mantendo `NetworkOnly` para
  mutações;
- se o service worker não confirmar o purge, as credenciais continuam
  revogadas e o novo pareamento permanece bloqueado com opção de nova tentativa.

## Evidência local

| Gate | Resultado |
| --- | --- |
| Driver Vitest | 5 ficheiros, 30 passed |
| Driver TypeScript | 0 erros |
| Build cliente com Vite bloqueado `5.4.21` | 1.808 módulos |
| Build PWA/service worker | 93 módulos; 6 entradas precache |
| Chromium | 2 passed |
| Não-vazamento | snapshot, fila, retry, descarte, cache, tokens e novo pareamento cobertos |

Os E2E confirmam dois percursos: cold start offline com snapshot da mesma
sessão e logout com eliminação de credenciais, stores e cache autenticado antes
de parear um novo motorista com novo `sessionId`.

## Limites de certificação

- O backend foi simulado no E2E; não houve staging nem Governance/backend real.
- Não houve dispositivo Android/iOS físico, rede móvel degradada, soak ou carga.
- Não houve revisão externa independente nem CI remota verde no SHA candidato.
- A base ROTAS original online não foi consultada, migrada ou modificada.
- Billing ROTAS não foi alterado.

## Decisão

- Critérios locais próprios do PR16 e gate G3: **verde local**.
- Integração da pilha PR15 + PR16: **pronta para revisão**, não certificada.
- Release global: **NO-GO** até CI remota, RC production-like, revisão
  independente e gates G4/G5.
