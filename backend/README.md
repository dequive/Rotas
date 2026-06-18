# ROTAS Backend

Primeiro slice backend/core do ROTAS MVP.

## Estrutura

- `app/main.py`: instancia FastAPI, health/version e routers `/api/v1`.
- `app/config.py`: settings por variaveis de ambiente.
- `app/database.py`: engine/session async SQLAlchemy e `Base`.
- `app/core/`: auth, tenant context, permissoes e envelope de erros.
- `app/modules/`: modulos de dominio com models, schemas, services e routers.

## Estado deste slice

Este slice cria a fundacao importavel e os modelos SQLAlchemy das tabelas MVP
centrais. Os routers expõem os endpoints principais. Os fluxos de contratos,
viagens/carga/cobranca, viaturas, motoristas, checklists e combustivel ja têm
serviços reais; alguns modulos secundarios ainda permanecem em stub incremental.

O endpoint `/api/v1/sync/batch` ja aplica idempotencia por tenant para escritas
offline vindas do PWA. Reenvios com a mesma chave e o mesmo payload devolvem o
resultado gravado; reutilizacao da chave com payload diferente devolve conflito.
O sync ja aceita criacao de `checklist`, `fuel_log`, `trip`, `trip_stop`,
`trip_cost`, `load_permit`, `cargo_manifest`, `transport_document` e
`delivery_proof`.

Nao ha integracoes externas reais neste slice. Presigned uploads, JWT real,
pairing de motorista, auditoria automatica, Cloudflare R2 real e regras de
negocio completas ficam para os slices seguintes. O modulo de ficheiros ja faz
upload local tenant-scoped para suportar recibos/fotos e exports PDF/XLSX no MVP
local.

## Verificacao local sugerida

```powershell
cd backend
python -m compileall app
```

Quando as dependencias estiverem instaladas:

```powershell
cd backend
uvicorn app.main:app --reload
```

## Migracoes

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "initial_schema"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Seed piloto

O seed piloto cria dados mínimos para demo e testes manuais: tenant, viatura pesada,
motorista, contrato de transporte de carga e template de checklist pre-partida.
O script é idempotente e pode ser corrido várias vezes sem duplicar dados.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.seed_pilot
```

Para criar uma viagem demo completa com Load Permit, manifesto, guia de
transporte, prova de descarga validada e documento de cobranca emitido:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.demo_pilot_flow
```
