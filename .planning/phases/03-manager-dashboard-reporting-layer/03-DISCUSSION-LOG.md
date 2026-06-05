# Phase 3: Manager Dashboard + Reporting Layer — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 03-manager-dashboard-reporting-layer
**Areas discussed:** Estilo de UI, KPI Dashboard, Export UX, Waiver UX

---

## Estilo de UI para novos componentes

| Option | Description | Selected |
|--------|-------------|----------|
| Continuar CSS custom | Manter consistência com ControlTowerOverview, CostMarginBoard, etc. sem novas dependências | |
| Introduzir Tailwind agora | O ROADMAP mencionava verificar Tailwind. Dois sistemas coexistem se migração parcial | ✓ |

**User's choice:** Introduzir Tailwind agora

**Sub-questão: Escopo da migração**

| Option | Description | Selected |
|--------|-------------|----------|
| Só componentes novos da Fase 3 | Componentes existentes ficam em CSS custom, novos usam Tailwind | |
| Migrar todos os componentes do manager | Refatorar tudo para Tailwind — base uniforme | ✓ |

**User's choice:** Migrar todos os componentes do manager

**Sub-questão: shadcn/ui**

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, instalar shadcn/ui | Button, Dialog, Table, Badge, Card prontos. Acelera waiver modal e KPI panels | ✓ |
| Não, Tailwind sem shadcn | Mais controlo, mas mais trabalho para modais e tabelas | |

**User's choice:** Sim, instalar shadcn/ui

---

## Localização do dashboard de KPIs (RPT-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Nova página /analytics dedicada | CT continua operacional diário, /analytics é vista estratégica separada | ✓ |
| Secção adicional na página principal | KPIs abaixo do CT na home — mais longa mas sem mudar rota | |
| Embebido nas páginas existentes | Métricas por viatura/motorista nos detalhes, sem vista consolidada | |

**User's choice:** Nova página /analytics dedicada

**Sub-questão: Filtros interativos**

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, filtros de período e viatura/motorista | Dropdown de período + filtro de viatura ou motorista. Queries parametrizadas no backend | ✓ |
| Fixo nos últimos 30 dias, sem filtros | Mais simples. Rolling 30 dias sem interação | |

**User's choice:** Sim, filtros de período e viatura/motorista

---

## UX de download de exports PDF/XLSX

| Option | Description | Selected |
|--------|-------------|----------|
| Polling com botão de download | Job ARQ → job_id → polling status → botão descarregar. Sem WebSocket | ✓ |
| Download síncrono | Gerar na request HTTP. Má UX para documentos grandes. Contra o ROADMAP | |
| Guardar e listar exports | Histórico de exports com links permanentes. Mais complexo | |

**User's choice:** Polling com botão de download

**Sub-questão: Formato de entrega**

| Option | Description | Selected |
|--------|-------------|----------|
| Streaming direto (blob) | Ficheiro servido como blob via endpoint autenticado | |
| URL pública temporária (signed URL) | S3/R2 com expiry. Mais adequado para grandes volumes e partilha | |

**User's choice:** "aplica o melhor metodo" → Claude's discretion (D-09: LOCAL_UPLOAD_DIR + endpoint autenticado)

---

## Fluxo de waiver para margens negativas (BILL-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Modal de aprovação inline | Botão na fila de billing → modal com detalhe de margem + justificativa | ✓ |
| Fila dedicada de waivers | Página separada para supervisores verem e aprovarem pedidos | |
| Aprovação por email | Supervisor recebe email com link — fora de escopo (notificações são v2) | |

**User's choice:** Modal de aprovação inline

**Sub-questão: Roles**

| Option | Description | Selected |
|--------|-------------|----------|
| Qualquer gestor solicita, só owner/admin aprova | Manager → solicita. Owner/admin → aprova. Alinha com RBAC existente | ✓ |
| Só supervisor cria e aprova diretamente | Uma única ação, sem workflow solicitar+aprovar | |

**User's choice:** Qualquer gestor pode solicitar, só owner/admin aprova

---

## Claude's Discretion

- Método exato de entrega de ficheiro de export (orientação D-09: LOCAL_UPLOAD_DIR + endpoint autenticado)
- Schema da tabela de waivers vs campo em billing_items
- Configuração ARQ workers (número, retry strategy)
- Animações/transições shadcn/ui
- Intervalo de polling de jobs e número máximo de tentativas

## Deferred Ideas

- Notificações email/WhatsApp para alertas de documentos — v2
- Scorecard de motoristas — Fase 4
- Signed URL para exports (S3/R2) — quando R2 for configurado
- WebSocket para CT em tempo real — nova infra, pós-MVP
- RLS PostgreSQL — Fase 4
