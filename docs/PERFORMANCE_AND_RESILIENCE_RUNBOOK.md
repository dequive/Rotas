# Runbook de Carga, Concorrência, Soak e Rede Degradada

Este runbook operacionaliza o PR-22. O contrato canónico está em
`infra/performance/PERFORMANCE_BUDGETS.json`; alterar um limite exige revisão
conjunta de Produto, QA e SRE e alinhamento com o catálogo SLO.

## Fronteiras de evidência

- `local_drill`: diagnóstico de engenharia. Nunca promove release.
- `staging_certification`: candidato a evidência de release, apenas no SHA do
  RC, com imagens imutáveis, `rotas_app`, dataset representativo e
  observabilidade activa.
- A injecção local de rede é client-side e determinística. Ela valida o
  comportamento da aplicação perante atraso/perda, mas não substitui um proxy
  TCP, dispositivo físico ou operador móvel real.
- O token é lido apenas de `ROTAS_PERF_TOKEN`; relatórios gravam
  `authorization: redacted`.

## Budgets bloqueantes

| Cenário | Budget principal |
| --- | --- |
| Leitura API | p95 <= 200 ms; p99 <= 500 ms; erros <= 1% |
| Batch offline, 5 operações | p95 <= 500 ms; p99 <= 1.000 ms; zero falhas de domínio |
| Corrida idempotente | 20 concorrentes; um efeito; zero conflitos |
| Rede degradada | 250 ms +/- 100 ms; 2% perda; p95 ponta-a-ponta <= 600 ms |
| Soak staging | mínimo 2 h; zero Sev-1/Sev-2 não resolvido |

Stock negativo, diário desequilibrado, leakage cross-tenant e efeitos
duplicados têm tolerância zero.

## Pré-condições de staging

1. Vincular base URL, imagens e deploy ao SHA integral do RC.
2. Confirmar `/version`, TLS, secrets externos e observabilidade PR-20.
3. Confirmar que `DATABASE_URL` usa `rotas_app`, sem superuser/BYPASSRLS.
4. Carregar dataset autorizado e representativo, com dois tenants.
5. Criar uma viatura, motorista e viagem exclusivos do ensaio por tenant.
6. Preparar o payload fora do repositório; IDs e token não entram em Git.
7. Registar baseline de CPU, memória, pools PostgreSQL/Redis, locks e filas.
8. Confirmar `pg_stat_statements` activo e resetar a janela imediatamente antes
   do ensaio, usando uma identidade administrativa auditada.

## Execução

No backend:

```powershell
$env:ROTAS_PERF_TOKEN='<token-efemero>'
.\.venv\Scripts\python.exe -m scripts.performance_gate `
  --base-url https://staging.example `
  --tenant-id '<tenant-id>' `
  --scenario api_read `
  --profile staging_certification `
  --requests 10000 `
  --output ..\docs\evidence\PR22_STAGING_API_READ.json
```

Uma execução `staging_certification` isolada produz
`release_evidence_fragment`; nunca promove G4 por si só.
Antes da execução, definir `ROTAS_RELEASE_SHA` com o SHA integral do RC. O
gerador rejeita volume inferior ao perfil, API local/HTTP ou ausência do
endpoint HTTPS externo de métricas.

Para `offline_sync_batch` e `idempotency_race`, acrescentar
`--payload <ficheiro-json>`. O template aceita `{{request_id}}`; cada operação
normal deve ter `local_id` e `idempotency_key` próprios. A corrida usa a mesma
chave em todas as chamadas e deve ser inédita.

Executar sequencialmente:

1. leitura nominal;
2. batch offline nominal;
3. corrida idempotente;
4. rede degradada;
5. soak de duas horas;
6. invariantes transaccionais e tenant isolation;
7. recolha dos painéis, logs e alertas no mesmo intervalo.

O perfil de staging requer `--requests` porque a execução deve ser
explicitamente limitada e auditável. Distribuição multi-node e proxy TCP são
executados pelo runner aprovado do ambiente; o script local não se declara
um gerador distribuído.

Quando `--metrics-url` é fornecido, cada relatório passa a incluir:

- ocupação e capacidade agregadas dos pools;
- p95/máximo do atraso de agendamento do event loop entre workers;
- p95/máximo de CPU agregada dos workers, expressa em equivalentes de core.

Um valor de CPU `2.0` significa aproximadamente dois cores consumidos pelo
conjunto de workers, não 200% de uma única thread. Estas séries não possuem
labels de tenant, utilizador, query ou conexão.

No fim de cada cenário, exportar de `pg_stat_statements` apenas query IDs,
contagem, tempo total/médio, rows e block I/O. Não incluir texto SQL, parâmetros
ou identificadores de negócio no artefacto versionado.

Preparar o bundle a partir do template
`infra/performance/PR22_CERTIFICATION_CONTEXT.example.json`. Os tokens continuam
fora do ficheiro e são fornecidos exclusivamente por
`ROTAS_PERF_TENANT_A_TOKEN` e `ROTAS_PERF_TENANT_B_TOKEN`.

Exportar as estatísticas SQL com uma credencial administrativa efémera:

```powershell
$env:ROTAS_PERF_ADMIN_DATABASE_URL='<url-administrativa-efemera>'
.\.venv\Scripts\python.exe -m scripts.export_pg_stat_statements `
  --output <directorio-evidencia>\PR22_PG_STAT_STATEMENTS.json
```

Validar o contexto e confirmar que ambos os tokens estão presentes:

```powershell
.\.venv\Scripts\python.exe -m scripts.performance_certification `
  --context <directorio-evidencia>\PR22_CERTIFICATION_CONTEXT.json `
  --require-token-env
```

O contexto falha se usar localhost/HTTP, tag mutável, runner co-localizado,
papel diferente de `rotas_app`, tenants repetidos, menos de quatro cenários,
soak inferior a 7.200 segundos ou export SQL com texto de query.

## Critério de encerramento

PR-22 só pode passar a `done` quando:

- todos os checks JSON são `true` no mesmo SHA do RC;
- volumes e cardinalidades são representativos;
- dois tenants passam sem leakage;
- corrida idempotente produz uma linha/efeito;
- não há stock negativo nem diários desequilibrados;
- métricas de sistema explicam a capacidade e não há saturação silenciosa;
- o ensaio TCP/rede móvel e o soak mínimo de duas horas passam;
- QA e SRE assinam o relatório.

Qualquer budget vermelho mantém G4 vermelho. Reduzir carga ou aumentar o
limite depois da falha exige uma decisão de capacidade documentada; não é uma
correcção automática.
