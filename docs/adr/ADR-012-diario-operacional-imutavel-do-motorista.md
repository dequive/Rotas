# ADR-012: Diário operacional imutável do motorista

## Status

Accepted — 2026-08-24

## Contexto

A PWA do motorista precisa permitir execução em campo sem transferir para o
motorista responsabilidades administrativas do gestor, tesouraria ou cliente.
Hoje, checklist, combustível e custos de viagem existem em domínios distintos,
mas não formam um histórico Driver público, uniforme e imutável. Em particular,
um abastecimento submetido ainda pode ter factos operacionais alterados no mesmo
registo, o que impede uma trilha enterprise confiável.

O Load Permit é emitido pelo cliente final/dono da carga, conforme a ADR-008.
No uso local, “despacho” também designa o valor entregue ao motorista para
despesas de uma viagem de longo curso; esse conceito não pode ser confundido
com a autorização operacional de saída.

## Decisão

O Driver terá um **Diário de viagem** tenant-scoped e driver-scoped, composto
por quatro tipos de registo:

| Tipo | Quem origina | O que o motorista pode fazer | Regra após submissão |
| --- | --- | --- | --- |
| Checklist | motorista | iniciar, preencher e submeter durante viagem atribuída ativa | respostas submetidas são imutáveis; correção gera nova versão ligada à original |
| Combustível | motorista | registar abastecimento e consultar verificação | litros, custo, posto, odómetro, pagamento e evidências são imutáveis; correção é ajuste/estorno referenciado |
| Despesa de viagem | motorista ou gestor, segundo política | registar com comprovativo e consultar validação | lançamento é append-only; rejeição, ajuste ou estorno não reescreve o original |
| Despacho de viagem | gestor/sistema/tesouraria | consultar e acusar receção | motorista nunca define, aprova, emite ou altera o valor; ajuste/estorno é novo movimento |

Aplicam-se ainda estas regras:

1. “Autorização de carregamento” é o rótulo principal na PWA; “Load Permit” é
   apenas explicação secundária. A origem visível é “Emitida pelo cliente/dono
   da carga”. O motorista só consulta ou solicita o documento em falta.
2. “Despacho de viagem” é o valor/allowance. “Autorização de saída” é o gate
   operacional. Os dois conceitos têm nomes, permissões e históricos distintos.
3. Registos só podem ser criados para viagem atribuída ao motorista autenticado
   e em estado operacional permitido. Depois de `delivered`, `closed` ou
   `cancelled`, o diário é somente leitura; a prova de descarga segue a sua
   máquina de estados própria.
4. A correção nunca usa `PATCH` destrutivo sobre factos submetidos. Cria um
   evento `adjustment`, `reversal` ou uma nova versão com `corrects_id`, motivo,
   autor, instante e idempotency key. Projeções podem mostrar o saldo/estado
   atual, mas preservam toda a cadeia.
5. Verificação, aprovação, rejeição e acusação de receção são eventos auditáveis,
   separados dos factos capturados pelo motorista.
6. API Driver usa DTOs públicos próprios e não expõe margem, preço interno,
   reconciliação financeira, conta contabilística ou dados de outro motorista.
7. Leitura offline e filas são particionadas por
   `(tenant_id, driver_id, device_id, session_id)`. Replays entre identidades
   falham fechados.
8. A leitura de despesas só publica movimentos marcados como pagos pelo
   motorista; custos internos pagos pela empresa não atravessam o contrato
   Driver. O despacho monetário é lido de `DriverAdvance`, não da projeção de
   custo `driver_despacho`.
9. Evidência sem download dedicado expõe apenas `has_receipt`; UUID de ficheiro,
   notas internas, referências de pedido e identidades de aprovação ficam fora
   do DTO público.

## Arquitetura de informação da PWA

A navegação canónica passa a ser:

- **Hoje**: próxima ação, viagem atual e alertas acionáveis;
- **Viagens**: atribuídas, entregues a aguardar fecho e histórico;
- **Registos**: todos, checklist, combustível, despesas e despacho de viagem;
- **Mais**: sincronização, dispositivo, ajuda e terminar sessão.

O detalhe da viagem agrupa `Resumo`, `Documentos`, `Registos` e `Ocorrências`.
Tarefas administrativas do gestor não aparecem como atalhos do motorista.

## Consequências técnicas

- remover `fuel_log` do conjunto de updates Driver/Sync para factos submetidos;
- introduzir contratos Driver paginados para o diário e detalhe por registo;
- modelar correções/estornos com referência ao original e unicidade idempotente;
- preservar o modelo append-only já existente em custos, acrescentando ator
  Driver explícito e contratos de leitura ownership-scoped;
- publicar histórico de checklist e combustível sem reutilizar serializers de
  gestor;
- testar estados ativos e terminais, ownership intra-tenant, replay, corrida,
  cache por identidade, correção e impossibilidade de alteração destrutiva;
- migrar a PWA para os tokens e primitives canónicos de `DESIGN.md`, com estados
  loading, empty, error, forbidden, degraded/offline e success.

## Critério de aceitação

Esta decisão só fica fechada quando backend, OpenAPI, cliente, PWA, testes
unitários/integrados/E2E e Android físico demonstrarem a mesma jornada no mesmo
SHA/artefacto. A aprovação desta ADR não promove C2 nem qualquer gate de release.

Em 2026-08-24, quatro coleções públicas foram implementadas sob
`/driver/records`: `checklists`, `fuel`, `expenses` e `advances`. Todas são
paginadas, aceitam filtro opcional por viagem e falham fechadas para outro
motorista. A partição Driver/OpenAPI passou `58/58`; a regressão integral numa
base descartável `template0 -> rec15` passou `1003/1003`; Ruff e Pyright globais,
OpenAPI SHA-256 `00305475b9625a65ad53d0f8162e63ba0e738c4f35269e242be7254b39690f0c`,
cliente gerado e Manager typecheck ficaram verdes.

O incremento seguinte implementou `rec16`: despesas guardam snapshot do
motorista, visibilidade e ator; o backfill é determinístico pela viagem/origem;
`UPDATE/DELETE` falha na base e ajuste/estorno são movimentos referenciados,
idempotentes, auditados e reconciliados. Partição integrada `81/81`, regressão
descartável `1009/1009`, Ruff/Pyright, OpenAPI `be1f22...2049d`, Manager
`128/128`, auditor `208/158/0` e build 74 páginas ficaram verdes.

O incremento PWA seguinte publicou o diário com cache Dexie segregado por
tenant, motorista e sessão, estados completos e navegação
Hoje/Viagens/Registos/Mais. A passagem física pós-CORS no Redmi provou que as
quatro chamadas chegam ao backend e não expõem códigos internos; revelou uma
sessão legada sem refresh token, expirada em 2026-08-21. A recuperação passa a
oferecer `Voltar a emparelhar`; um segundo teste RED impediu purge imediato e
exige confirmação `Limpar e emparelhar` antes da limpeza fail-closed. Driver
passou `56/56`, typecheck, build `1805/93/6` e Playwright mobile `7/7`. O Redmi
confirmou a primeira ação no bundle intermédio.

Após autorização explícita, o Redmi executou o segundo passo e voltou à tela de
emparelhamento. Access/refresh/tenant/driver/session ficaram ausentes; todos os
stores `RotasMotoristaDB` e a fila Workbox foram contados a zero. O slice visual
seguinte fixa a navegação ao viewport, cobre safe areas/`100dvh`, ocupa 390 e
412 px integralmente e alinha a entrada com o contrato backend de seis dígitos
numéricos, validade de 15 minutos e erro operacional sem código interno. Driver
passou `60/60`, build `1806/93/6` e Playwright `7/7`. O bundle foi carregado e a
ativação autónoma foi inspecionada no Redmi. A origem instalada `4173` reteve
cliente/precache antigo; após saída real, 18 stores e Workbox ficaram a zero,
mas a atualização exigiu recuperação manual. RED/GREEN preserva agora o worker
pré-mount e mostra `Atualizar aplicação` sem sessão. Naquele ponto faltavam a
prova física entre versões, pairing com refresh token e diário online/degradado
no mesmo SHA/artefacto. C2 e release continuavam `NO-GO`.

O incremento de origem/atualização fixa `http://localhost:4173` como única
origem local instalável, de preview e E2E; `4174` é rejeitada e `5174` é somente
desenvolvimento. Configuração e manifesto passam a fonte única, com porta
estrita e loader Vite nativo. Uma instalação já controlada verifica e ativa a
versão nova antes do render; primeira instalação não espera o worker, e o cold
start offline mantém o cache. A prova Redmi expôs bind IPv6-only; o preview
passou a bind técnico `0.0.0.0` sem alterar a origem `localhost:4173`, mantendo
somente reverses 4173/8000. O WebAPK autónomo migrou de
`index-tVgRH7eW.js` para `index-GP13naLz.js`; um update seguinte, já conduzido
pelo lifecycle novo, ativou sem erros e removeu o JS antigo de `static-assets`.
Ficou um alvo standalone, worker ativo/controlador e sem waiting/installing.
Driver `67/67`, typecheck, build `1806/94/6`, E2E `7/7` e CORS isolado `5/5`
estão verdes. Pairing e diário online/degradado no mesmo SHA/artefacto continuam
pendentes; aceitação C2 permanece aberta.
