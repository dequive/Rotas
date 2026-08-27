# PR-14 — Operação de Retry, DLQ e Reconciliação

Data da evidência: 2026-07-27  
Estado: `done_local`  
Gate associado: G3 — Reliability and Offline

## Resultado local

O transactional outbox passou a ter uma superfície operacional tenant-scoped:

- `GET /api/v1/outbox-events`: lista eventos com filtros de estado, tipo,
  agregado e correlação;
- `GET /api/v1/outbox-events/reconciliation`: apresenta saúde e contagens
  locais de pending, due, sent, dead-letter, sent sem timestamp e entregas
  Governance sem `case_id` registado;
- `GET /api/v1/outbox-events/{id}`: detalhe autorizado, incluindo payload;
- `POST /api/v1/outbox-events/{id}/replay`: recoloca exclusivamente eventos
  dead-letter em pending.

As permissões `outbox.read` e `outbox.replay` foram atribuídas apenas aos
papéis tenant `owner` e `admin`. Todas as consultas e locks incluem
`tenant_id`; um ID pertencente a outro tenant devolve 404 estrito.

## Replay e concorrência

O replay:

1. exige motivo entre 10 e 500 caracteres;
2. bloqueia a linha com `FOR UPDATE`;
3. aceita apenas estado `dead_letter`;
4. preserva o mesmo ID do evento e, portanto, a mesma identidade idempotente
   de entrega;
5. repõe `attempt_count=0`, limpa o erro e agenda tentativa imediata;
6. grava `outbox.dead_letter_replayed` no audit log na mesma transação;
7. descarta o alerta de DLQ associado;
8. responde de forma idempotente quando o evento já está pending.

Duas requisições concorrentes foram testadas: exactamente uma realizou a
transição e apenas um audit log foi criado.

## Métricas e alertas

O drainer publica o contador Prometheus
`rotas_outbox_delivery_outcomes_total{outcome,event_kind}` sem labels de tenant
ou evento, evitando cardinalidade descontrolada.

Cada transição para dead-letter cria ou reactiva um alerta dashboard high com
referência determinística `outbox-dlq:{event_id}`. A unicidade existente em
`tenant_id + request_reference` impede alertas duplicados.

O endpoint de reconciliação classifica:

- `red`: existe dead-letter ou sent sem `sent_at`;
- `yellow`: existem pending vencidos ou entrega Governance sem case ID local;
- `green`: nenhuma destas condições locais foi encontrada.

Esta reconciliação é deliberadamente local. Não prova, por si só, que o estado
do Governance remoto coincide com o ROTAS.

## CLI operacional

O script `backend/scripts/outbox_ops.py` oferece os comandos `list`, `show`,
`reconciliation` e `replay`. O token só é lido de
`ROTAS_ACCESS_TOKEN`, evitando exposição em argumentos do processo.

Exemplo:

```powershell
$env:ROTAS_API_URL='https://rotas.example'
$env:ROTAS_ACCESS_TOKEN='<token>'
$env:ROTAS_TENANT_ID='<tenant-uuid>'
.\.venv\Scripts\python.exe scripts\outbox_ops.py reconciliation
.\.venv\Scripts\python.exe scripts\outbox_ops.py list --status dead_letter
.\.venv\Scripts\python.exe scripts\outbox_ops.py replay <event-id> --reason 'Contrato upstream corrigido.'
```

## Gates reproduzidos

```text
Ruff focado:                         green
Pyright focado:                      0 erros, 0 warnings
Pytest outbox/integracoes/OpenAPI:   22 passed
OpenAPI check:                       green
Manager generated API check:         green
Manager TypeScript:                  green
```

Contrato OpenAPI:

```text
304 paths
371 operations
218 schemas
sha256=d0b86b2b039aa5f191d74139550b497cf13e2fc65e549e763d5307bdbc66f777
```

O aviso único de Pytest foi o fallback deliberado do rate limiter para memória
porque `REDIS_URL` foi removido no teste local.

## Evidência ainda necessária para G3 verde

- executar a CLI/API contra o SHA do release candidate;
- produzir e recuperar uma DLQ real em staging;
- confirmar entrega do alerta pelo canal operacional e escalonamento;
- reconciliar ROTAS e Governance reais, incluindo casos 201 e replay 409;
- provar métricas, dashboards e alertas no stack de observabilidade;
- validar recovery sob indisponibilidade, concorrência e rede degradada.

Assim, PR-14 está `done_local`, mas G3 permanece amarelo.
