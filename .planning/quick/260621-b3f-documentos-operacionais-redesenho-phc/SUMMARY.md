# 260621-b3f — Redesenho Documentos Operacionais PHC

**Status:** DONE  
**Commit:** 96b70ed  
**Date:** 2026-06-21

## O que foi feito

Redesenho completo de 2 documentos existentes e criação de 3 novos, todos com layout PHC institucional consistente.

### Documentos redesenhados
- **Guia de Remessa** (`cargo/exporters.py`) — cabeçalho 2 colunas (emitente / DESTINATÁRIO box), barra metadados, tabela de carga com bordas, bloco rota, 3 assinaturas
- **Carta de Porte Internacional** (`cargo/exporters.py`) — cabeçalho bilingue PT/EN, metadados fronteiriços, bloco expedidor/consignatário, declaração aduaneira, 3 assinaturas

### Documentos criados
- **Relatório de Viagem** (`trips/exporters.py` + `GET /api/v1/trips/{id}/report/pdf`) — box VIAGEM com placa/motorista, metadados Origem→Destino, tabela paragens, financeiro 2 colunas
- **Ordem de Serviço** (`workshop/exporters.py` + `GET /api/v1/workshop/work-orders/{id}/pdf`) — box VIATURA, diagnóstico + trabalho planeado, tabela tarefas h/min, custos comparativos verde/vermelho
- **Inspecção de Viatura** (`checklists/exporters.py` + `GET /api/v1/checklists/{id}/pdf`) — grid 2 colunas com pills OK/NOK/N/A coloridos, observações, assinatura motorista

## Padrão PHC aplicado
- Cabeçalho 2 colunas: emitente esq (TenantDocumentProfile) + entity box dir (navy header + bordas)
- Barra metadados cinza `_SOFT` com doc label em navy à direita
- Section headers navy preenchidos
- Rodapé normalizado: "Documento Processado por Computador — ROTAS — Página N de T"
- Paleta: `_NAV=(16,32,51)`, `_SOFT=(245,247,250)`, `_LINE=(216,222,232)`, `_AMBER=(245,158,11)`

## Ficheiros alterados
- `backend/app/modules/cargo/exporters.py` — redesenhado
- `backend/app/modules/trips/exporters.py` — criado
- `backend/app/modules/trips/router.py` — endpoint PDF adicionado
- `backend/app/modules/workshop/exporters.py` — criado
- `backend/app/modules/workshop/router.py` — endpoint PDF adicionado
- `backend/app/modules/checklists/exporters.py` — criado
- `backend/app/modules/checklists/router.py` — endpoint PDF adicionado

## Verificação
- `ruff check` → 0 erros em todos os 7 ficheiros
- Smoke test: 3 novas rotas visíveis em `app.routes` (`/api/v1/trips/{id}/report/pdf`, `/api/v1/workshop/work-orders/{id}/pdf`, `/api/v1/checklists/{id}/pdf`)
- Zero novas dependências, zero migrações
