# PR-22 — Diagnóstico e Optimização de Performance

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations  
SHA base: `d8a8e52b5f1cb98ef4fd805c945fd70674c98e25` + working tree

## Veredicto

Foram removidos round-trips e commits redundantes, com melhoria material no
sync e na corrida idempotente. Os budgets continuam vermelhos: a leitura
aquecida ficou 15,5 ms acima do p95 permitido, o sync mostrou timeouts numa
das repetições e a corrida continuou acima de 500 ms.

Nenhum threshold foi aumentado. O experimento de pool que não mostrou ganho
foi revertido.

## Ambiente production-like local

- quatro workers Uvicorn, correspondentes aos quatro workers do container;
- `ENVIRONMENT=production`, JSON logging e access log Uvicorn desligado;
- JWTs reais dashboard/driver, sem `DEV_TEST_TOKEN`;
- `DATABASE_URL` com `rotas_app`, confirmada `NOSUPERUSER` e sem `BYPASSRLS`;
- `ADMIN_DATABASE_URL` separada com `rotas_admin`;
- PostgreSQL 16/`rec13` e Redis locais;
- tenant, utilizador, motorista, dispositivo e viagem sintéticos;
- R2, SMTP, domínio e TLS eram apenas configuração local não exercitada.

As passwords dev das roles locais estavam divergentes da inicialização
versionada. Foram reconciliadas para os valores já declarados em
`infra/postgres-init.sql`; nenhuma credencial de produção foi usada.

## Alterações mantidas

### Validação de identidade

O dashboard fazia `Tenant.get` e `User.get` sequenciais em cada pedido. O
driver fazia consultas separadas para tenant, motorista e dispositivo. Cada
percurso agora usa uma única consulta administrativa com `outer join`:

- revogação continua validada em cada pedido;
- nenhum cache de identidade foi introduzido;
- os erros tipados `tenant_inactive`, `user_inactive`, `driver_inactive` e
  `driver_access_revoked` foram preservados.

### Batch offline

Um batch de cinco operações executava cinco commits. Batches multi-operação
agora:

1. convertem commits internos dos serviços em flushes;
2. persistem todas as operações numa transação exterior;
3. fazem um único commit;
4. perante corrida de idempotência, fazem rollback e reconciliam pelo percurso
   sequencial idempotente já estabelecido.

Batches vazios ou de uma operação mantêm o comportamento anterior.

Uma iteração posterior acrescentou prefetch tenant-scoped das chaves de
idempotência: batches multi-operação fazem um SELECT em vez de um por operação.
O detalhe de fase e a ausência de melhoria de cauda estão documentados em
`PR22_PERFORMANCE_DIAGNOSTICS_20260727.md`.

## Resultados

### Leitura

| Execução | p50 | p95 | p99 | Erros | Estado |
| --- | ---: | ---: | ---: | ---: | --- |
| production-like antes da alteração | 100,442 ms | 261,798 ms | 1.110,499 ms | 0/600 | red |
| código optimizado, primeira execução | 104,411 ms | 282,533 ms | 1.251,901 ms | 0/600 | red |
| código optimizado, aquecido | 77,552 ms | 215,499 ms | 337,901 ms | 2/600 timeouts | red |

A consolidação reduz trabalho SQL, mas a variabilidade local impede declarar
o budget de 200 ms aprovado.

### Sync multi-operação

| Execução | Efeitos observados | p95 | p99 | Erros | Estado |
| --- | ---: | ---: | ---: | ---: | --- |
| primeira optimizada | 500/500 | 521,481 ms | 588,391 ms | 0/100 | red p95 |
| repetição com chaves novas | 475/500 | 423,281 ms | 10.071,934 ms | 5/100 timeouts | red |

A baseline anterior tinha p95 780,602 ms. A comparação é indicativa, não uma
certificação A/B estrita, porque a baseline anterior usava um worker e token
de desenvolvimento, enquanto esta execução usou quatro workers, JWT real e
`rotas_app`.

### Corrida idempotente

Vinte chamadas concorrentes com chave inédita:

- 20 respostas 200;
- zero conflitos;
- uma linha de idempotência;
- um efeito de negócio;
- p95 750,048 ms e p99 763,696 ms;
- budget p95 500 ms: red.

A baseline anterior tinha p95 2.080,793 ms, sob topologia local diferente.

## Experimentos rejeitados

Redistribuir o pool de `2 + 3 overflow` para `3 + 2 overflow`, mantendo o mesmo
teto, produziu leitura p95 275,978 ms. Sem ganho comprovado, a alteração foi
revertida e não integra o produto.

## Invariantes e regressão

```text
Sync optimizado 1:          500 efeitos processados
Sync optimizado 2:          475 efeitos; 5 pedidos expiraram sem efeito
Corrida idempotente:        1 linha / 1 efeito
Stock negativo:             0
Diários desequilibrados:    0
Pytest auth/sync/RLS:        37 passed
Ruff:                       green
Pyright app + tests:        0 erros, 0 warnings
Validador PR-22:             green
```

## Artefactos JSON

- `PR22_LOCAL_API_READ_PRODLIKE_20260727.json`;
- `PR22_LOCAL_API_READ_OPTIMIZED_20260727.json`;
- `PR22_LOCAL_API_READ_OPTIMIZED_WARM_20260727.json`;
- `PR22_LOCAL_SYNC_OPTIMIZED_20260727.json`;
- `PR22_LOCAL_SYNC_OPTIMIZED_REPEAT_20260727.json`;
- `PR22_LOCAL_RACE_OPTIMIZED_20260727.json`;
- `PR22_LOCAL_API_READ_POOL_OPTIMIZED_20260727.json`.

## Próximo bloqueio técnico

1. instrumentar tempo de fila do pool, auth, RLS e handler separadamente;
2. activar `pg_stat_statements` no staging e correlacionar com PR-20;
3. eliminar as timeouts de 10 s antes de qualquer aumento de carga;
4. repetir com gerador externo, imagens do RC e recursos limitados como em
   produção;
5. executar dois tenants, proxy TCP/rede móvel e soak mínimo de duas horas.

PR-22 permanece `in_progress`; G4 permanece vermelho.
