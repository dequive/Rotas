# ROTAS

Plataforma de gestao total de frotas para operadores mocambicanos, com foco em operacao offline-first, prova documental, controlo de viagens, combustivel, carga e cobranca contratual.

## Linha de Base

- Instruções canónicas para agentes: `AGENTS.md`
- Estado atual e convergência: `docs/CURRENT_STATE_AND_CONVERGENCE_PLAN_20260822.md`
- Normas de engenharia: `docs/ENGINEERING_STANDARDS.md`
- Plano mestre integrado de implementacao: `docs/ROTAS_MASTER_DELIVERY_PLAN.md`
- Matriz de fecho: `docs/MODULE_CLOSURE_MATRIX.md`
- Decisão GO/NO-GO: `docs/PRODUCTION_RELEASE_LEDGER.md`

`ROTAS_Plano_Mestre_Execucao.md`, `ROTAS_Especificacao_Tecnica_MVP.md` e análises
históricas são referências de origem, não fontes vinculativas do estado atual.

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

Projeto em beta interno avançado e estabilização pré-RC. A base técnica é ampla,
mas a auditoria de 2026-08-22 confirmou bloqueios P0 em Driver/Sync, linhas Git
divergentes e ausência de CI/staging/piloto no mesmo SHA. A decisão atual é
`NO-GO` para merge do PR #44, piloto, comercialização e produção.

Issue #42 e C0-C4 do plano de convergência precedem Issue #43 e novas funções.

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

Manager e PWA devem usar autenticação real. Dados demo e tokens de desenvolvimento
não constituem evidência. O Driver é emparelhado por código one-time e a validação
de produto exige uma viagem atribuída pelo gestor, operação offline e
reconciliação posterior; consultar a baseline antes de executar o piloto.
