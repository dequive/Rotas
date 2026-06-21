# Quick Task 260621-uvf — SUMMARY

**Task:** Fase 0 — auditoria de dados clients→third_parties  
**Date:** 2026-06-21  
**Status:** Concluído

## O que foi feito

Executadas 4 queries de auditoria SELECT contra `postgresql://rotas:rotas@localhost:55432/rotas` via asyncpg (backend/.venv). Resultados escritos em `260621-uvf-REPORT.md`.

## Resultados

| Query | Resultado |
|---|---|
| clients total | **2 213** |
| third_parties total | **1 090** |
| clients com nuit NULL | **0** (100% preenchidos) |
| NUITs duplicados por tenant | **0** |
| Sobreposição clients ∩ third_parties | **0** |

## Classificação de Risco Fase A: **MÉDIO**

Todas as condições de risco ALTO são falsas. Os dados estão limpos:
- Zero NUITs nulos — backfill sem bloqueadores
- Zero duplicados — `UNIQUE (tenant_id, nuit)` pode entrar sem conflito
- Zero sobreposição — migração é criação pura, sem fusão

## Decisão desbloqueada

**Pergunta 2 do design respondida:** Fase única de migração é viável. Paralelismo permanente (clients como view) seria dívida sem justificação de segurança — os dados não têm sujidade que o justifique.

## Artefactos

- `260621-uvf-REPORT.md` — relatório completo com números e implicações
