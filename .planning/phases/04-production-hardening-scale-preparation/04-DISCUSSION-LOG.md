# Phase 4: Production Hardening + Scale Preparation — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — este log preserva as alternativas consideradas.

**Date:** 2026-06-05
**Phase:** 04-production-hardening-scale-preparation
**Areas discussed:** MAINT-01 Scheduler, Driver Scorecard, Escalabilidade/Gunicorn, RLS

---

## MAINT-01: Scheduler Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Cron diário | ARQ worker corre uma vez por dia | |
| Evento de odómetro | Trigger imediato quando odómetro é actualizado | |
| Combinado: cron + evento | Evento para captura rápida + cron como safety net | ✓ |

**Decisão:** Trigger combinado — evento de odómetro (imediato) + cron diário (safety net para planos por calendário).

---

## Reset do MaintenanceSchedule

| Option | Description | Selected |
|--------|-------------|----------|
| Marcar como triggered, criar nova entrada | status='triggered' + nova entrada para próximo ciclo | ✓ |
| Reset in-place | Actualiza a mesma entrada com novos limiares | |
| Deixar ao planner | Decisão técnica para o planner | |

**Decisão:** Marcar como `triggered`, criar nova entrada para o próximo ciclo (histórico preservado).

---

## Quando o WorkOrder é fechado

| Option | Description | Selected |
|--------|-------------|----------|
| Não faz nada | Próximo schedule já criado no trigger | ✓ |
| Cria próximo schedule ao fechar | Reset baseado no odómetro do momento do fecho | |

**Decisão:** Sem side effects ao fechar — próximo schedule criado no momento do trigger.

---

## Alertas proactivos

| Option | Description | Selected |
|--------|-------------|----------|
| Sim — 30 dias/500 km antes | Alerta iminente no dashboard | ✓ |
| Não — só quando vence | Sem alertas de aproximação | |

**Decisão:** Alertas proactivos para manutenção iminente (≤30 dias ou ≤500 km do limiar).

---

## ARQ Worker para scheduler

| Option | Description | Selected |
|--------|-------------|----------|
| Mesmo worker, nova task | Partilha ARQ worker do CT-02 | ✓ |
| Worker separado | Processo dedicado para manutenção | |

**Decisão:** Mesma instância ARQ worker, nova task de manutenção.

---

## Duplicado de WorkOrder

| Option | Description | Selected |
|--------|-------------|----------|
| Skip silencioso | Se WO aberto existe, não criar duplicado | ✓ |
| Criar mesmo assim | Sempre criar novo WO | |

**Decisão:** Skip silencioso se WorkOrder aberto para o mesmo plan_id + vehicle_id.

---

## Driver Scorecard: Métricas

| Option | Description | Selected |
|--------|-------------|----------|
| Distância percorrida (km) | Total km por viagem | ✓ |
| Taxa de entrega comprovada | % viagens com delivery proof | ✓ |
| Pontualidade de sync | Batches sync por viagem | ✓ |
| Duração de paradas | Tempo médio de parada / distância | ✓ |

**Decisão:** Todas as 4 métricas incluídas. Ponderação exacta ao critério do planner.

---

## Apresentação do Score

| Option | Description | Selected |
|--------|-------------|----------|
| Score 0-100 com código de cor | Verde ≥80, amarelo 60-79, vermelho <60 | ✓ |
| Métricas separadas sem score único | Granular, sem agregação | |
| Grade A/B/C/D/F | Estilo académico | |

**Decisão:** Score 0-100 com cores.

---

## Período de Cálculo

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling 30 dias | Janela móvel — desempenho recente | ✓ |
| Mês calendário actual | Reseta início do mês | |
| Acumulado de todas as viagens | Histórico total | |

**Decisão:** Rolling 30 dias.

---

## Visibilidade do Scorecard

| Option | Description | Selected |
|--------|-------------|----------|
| Só gestor no dashboard | Sem alterações ao PWA | ✓ |
| Gestor + motorista no PWA | Requer alterações ao driver PWA | |

**Decisão:** Apenas gestor no manager dashboard.

---

## Escalabilidade: Backend

| Option | Description | Selected |
|--------|-------------|----------|
| Gunicorn + UvicornWorker | 4 workers, controlo de processos via gunicorn | ✓ |
| Uvicorn --workers flag | Mais simples, menos controlo | |
| Escala horizontal Railway | Mais caro | |

**Decisão:** Gunicorn + UvicornWorker, 4 workers baseline.

---

## ARQ Worker Deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Serviço separado no Railway | Isolamento de falhas | ✓ |
| Mesmo processo via threading | asyncio + threading — não recomendado | |

**Decisão:** Serviço Railway separado para ARQ worker.

---

## Composite Index Audit

| Option | Description | Selected |
|--------|-------------|----------|
| EXPLAIN ANALYZE nas 10 queries mais comuns | Data-driven, sem indexes desnecessários | ✓ |
| Adicionar todos preventivamente | Simples mas pode ser excessivo | |
| Deixar ao planner | Decisão técnica | |

**Decisão:** EXPLAIN ANALYZE approach — data-driven.

---

## RLS: Fase 4 ou v2?

| Option | Description | Selected |
|--------|-------------|----------|
| Adiar para v2 | Phase 4 já tem scope suficiente | |
| Incluir na Phase 4 | Defense-in-depth a nível de base de dados | ✓ |

**Decisão:** Incluir na Phase 4.

---

## RLS Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| SET LOCAL via SQLAlchemy event | Sem alterações nos queries existentes | ✓ |
| Connection pooling por tenant | Impraticável com N tenants dinâmicos | |

**Decisão:** SET LOCAL app.tenant_id via SQLAlchemy event listener.

---

## RLS Bypass para Admin/Worker

| Option | Description | Selected |
|--------|-------------|----------|
| Role BYPASSRLS para admin/worker | rotas_app + rotas_admin roles separados | ✓ |
| NULL = bypass | Menos seguro | |

**Decisão:** Dois roles: `rotas_app` (RLS activo) e `rotas_admin` (BYPASSRLS).

---

## Claude's Discretion

- Ponderação exacta das métricas do scorecard (planner propõe fórmula razoável)
- Tabelas específicas para RLS policies (researcher determina via análise do schema)
- Número exacto de Gunicorn workers (ajustável conforme RAM Railway)

## Deferred Ideas

- Scorecard visível ao motorista no PWA — adiado para depois da Phase 4
- Notificações email/WhatsApp para manutenção iminente — v2
- RLS foi considerado para v2 mas decidido incluir na Phase 4
