# PR15 — Lifecycle offline do Driver na pilha de estabilização

Data: 2026-08-09

Branch: `codex/pr15-driver-offline`

Base: `ecd8a37` (`codex/pr14-outbox-resilience`)

## Resultado

Estado: **done_local para os critérios de engenharia do PR15**; **não
certificado para release**.

O Driver passou a manter um lifecycle offline explícito e observável:

- Dexie v2 persiste `lastAttemptAt`, `nextAttemptAt` e `deadLetteredAt` nas
  filas sem remover stores existentes;
- Dexie v3 guarda o bootstrap por `tenantId:driverId`;
- falhas transitórias usam backoff exponencial persistente, jitter e limite de
  cinco tentativas;
- a quinta falha entra em `dead_letter` em vez de permanecer invisível;
- itens abandonados em `syncing` regressam a `retrying` no arranque;
- `401` tenta renovar a sessão uma vez e conserva a tentativa quando não há
  refresh possível;
- conflitos, falhas terminais e dead letters ficam visíveis e podem ser
  reenfileirados com nova `Idempotency-Key` ou descartados com confirmação;
- o descarte de um registo remove a operação, fotografias associadas e o
  registo de combustível numa única transação Dexie;
- a recuperação da rede dispara sincronização imediata e mantém verificação a
  cada 30 segundos, com lock local contra ciclos concorrentes.

## Cache e service worker

- `GET /api/v1/driver/bootstrap` é `NetworkOnly` no Workbox; o cache HTTP
  partilhado não pode servir bootstrap autenticado offline.
- O cold start só usa o snapshot Dexie cuja chave coincide com tenant e
  motorista autenticados.
- Sem snapshot válido, viagem, checklist, combustível, manifesto, prova de
  entrega e paragens permanecem bloqueados.
- `POST /api/v1/sync/batch` é `NetworkOnly`; o plugin Background Sync recebe
  apenas falhas de rede e a fila Dexie continua a ser o estado operacional
  canónico da aplicação.
- A chave idempotente é enviada no cabeçalho e no corpo e é preservada até
  reconciliação bem-sucedida.

## Evidência local

| Gate | Resultado |
| --- | --- |
| Driver Vitest | 4 ficheiros, 24 passed |
| Driver TypeScript | 0 erros |
| Build cliente com Vite bloqueado `5.4.21` | 1.807 módulos |
| Build PWA/service worker | 93 módulos; 6 entradas precache |
| Chromium cold start | 1 passed |
| Idempotência observada | mesma chave no header e payload; segunda reconciliação ausente |

O E2E abre o PWA online, persiste o bootstrap, fecha a página, reabre o mesmo
contexto totalmente offline, recupera a viagem, prova que o bootstrap não está
no `api-cache`, cria uma operação local e confirma uma única sincronização ao
regressar a rede.

## Fronteira explícita com PR16

Este PR não antecipa o isolamento de sessão do PR16:

- as filas operacionais ainda não possuem a chave composta
  `tenantId + driverId + sessionId`;
- logout/troca de identidade ainda não faz purge fail-closed de IndexedDB,
  Cache Storage e fila Workbox;
- o PR15 não deve ser promovido isoladamente para release antes do PR16 e dos
  seus testes de leakage.

## Limites de certificação

- O backend foi simulado no E2E; não houve staging nem Governance/backend real.
- Não houve dispositivo Android/iOS físico, instalação prolongada, rede móvel
  degradada, relógio divergente, carga ou soak.
- Não houve revisão externa independente nem CI remota verde no SHA candidato.
- A base ROTAS original online não foi consultada, migrada ou modificada.
- Billing ROTAS não foi alterado.

## Decisão

- Critérios locais próprios do PR15: **verde**.
- Integração/release isolada do PR15: **NO-GO** até PR16.
- Release global: **NO-GO** até CI remota, RC production-like, revisão
  independente e gates G4/G5.
