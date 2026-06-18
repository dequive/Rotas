# ROTAS

Plataforma de gestao total de frotas para operadores mocambicanos, com foco em operacao offline-first, prova documental, controlo de viagens, combustivel, carga e cobranca contratual.

## Linha de Base

- Plano mestre: `ROTAS_Plano_Mestre_Execucao.md`
- Especificacao tecnica MVP: `ROTAS_Especificacao_Tecnica_MVP.md`
- Analise de absorcao Kimi: `ROTAS_Analise_Absorcao_Kimi.md`
- Normas de engenharia: `docs/ENGINEERING_STANDARDS.md`
- Plano mestre integrado de implementacao: `docs/ROTAS_MASTER_DELIVERY_PLAN.md`

## Decisoes Nao Negociaveis

- MVP em monolito modular FastAPI.
- PWA motorista com IndexedDB/Dexie.js, nao SQLite.
- Multi-tenancy com `tenant_id` no service layer e RLS como defesa adicional.
- Alertas internos antes de WhatsApp completo.
- SQL documental e blueprint; migrations reais via Alembic.

## Dominios do MVP

- auth
- tenants/users
- drivers/devices
- vehicles
- files
- checklists
- fuel
- fuel operations
- workshop operations
- trips/cargo
- billing
- alerts
- sync/idempotency
- audit

## Estado

Projecto em fase de MVP tecnico com backend modular, dashboard gestor, PWA motorista,
infraestrutura local e Alembic. Os fluxos reais ja implementados incluem contratos,
viagens/carga/cobranca, viaturas, motoristas, checklists, combustivel e sync
offline idempotente.

## Execucao Local

```powershell
docker compose --file infra\docker-compose.yml up -d postgres redis
npm install
npm run typecheck
npm --workspace apps/manager run build
```

No Windows/OneDrive, se o build do PWA motorista falhar por permissao ao resolver o `HOME`:

```powershell
$env:HOME='C:\tmp'
$env:USERPROFILE='C:\tmp'
npm --workspace apps/driver run build
```

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "initial_schema"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Dados piloto:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.seed_pilot
.\.venv\Scripts\python.exe -m scripts.demo_pilot_flow
```

Dashboard gestor ligado a API:

```powershell
$env:ROTAS_API_BASE_URL='http://localhost:8000'
$env:ROTAS_TENANT_ID='<tenant_id devolvido por scripts.seed_pilot>'
$env:ROTAS_MANAGER_TOKEN='dev-token'
npm --workspace apps/manager run dev
```

Sem `ROTAS_TENANT_ID`, a tela de cobranca usa dados de demonstracao e mostra o
aviso no topo da pagina.

PWA motorista ligado a API:

```powershell
$env:VITE_ROTAS_API_BASE_URL='http://localhost:8000'
$env:VITE_ROTAS_TENANT_ID='<tenant_id devolvido por scripts.seed_pilot>'
$env:VITE_ROTAS_VEHICLE_ID='<vehicle_id devolvido por scripts.seed_pilot>'
$env:VITE_ROTAS_DRIVER_ID='<driver_id devolvido por scripts.seed_pilot>'
$env:VITE_ROTAS_CHECKLIST_TEMPLATE_ID='<checklist_template_id devolvido por scripts.seed_pilot>'
$env:VITE_ROTAS_DRIVER_TOKEN='dev-token'
npm --workspace apps/driver run dev
```

As telas de checklist e combustivel guardam registos offline na IndexedDB,
sincronizam fotos primeiro via `/api/v1/files/upload` e depois enviam os dados
operacionais via `/api/v1/sync/batch`.
