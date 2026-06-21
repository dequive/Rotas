# Fase 0 — Relatório de Auditoria de Dados

**Data:** 2026-06-21  
**BD:** `postgresql://rotas:rotas@localhost:55432/rotas`  
**Classificação de risco Fase A:** **MÉDIO**

---

## Resultados das 4 Queries

### Q1 — Volume Base

| Tabela | Registos |
|---|---|
| `clients` | **2 213** |
| `third_parties` | **1 090** |

### Q2 — Qualidade do NUIT em `clients`

| nuit_nulo | nuit_ok |
|---|---|
| **0** | **2 213** |

100% dos clients têm NUIT preenchido. Zero bloqueadores de backfill por campo nulo.

### Q3 — NUITs Duplicados por Tenant em `clients`

**0 linhas.** Nenhum tenant tem dois clients com o mesmo NUIT.  
O constraint `UNIQUE (tenant_id, nuit)` pode ser criado directamente sobre os dados existentes sem conflito.

### Q4 — Sobreposição `clients` ∩ `third_parties` (por NUIT)

| ja_sobrepostos |
|---|
| **0** |

Nenhum client tem NUIT que já exista em `third_parties` no mesmo tenant.  
As duas tabelas são conjuntos completamente disjuntos hoje.

---

## Classificação de Risco: MÉDIO

### Porquê não ALTO

As três condições de risco ALTO estão todas falsas:

| Condição ALTO | Resultado | Bloqueador? |
|---|---|---|
| Q3 ≥ 1 linha (NUIT duplicado por tenant) | 0 linhas | ✓ Não |
| Q4 > 0 (sobreposição existente) | 0 | ✓ Não |
| nuit_nulo > 50% dos clients | 0% nulos | ✓ Não |

### Porquê não BAIXO

O volume não é trivial. 2 213 registos a migrar implica:
- Criar 2 213 registos em `third_parties`
- Criar 2 213 registos em `third_party_roles` (role `client`)
- Criar 2 213 registos em `client_profiles` (crédito, prazo)
- Popular `clients.third_party_id` com os UUIDs gerados
- Executar tudo em transacção única ou em lotes com rollback seguro

O risco é de **execução e atomicidade**, não de qualidade de dados.

---

## Implicações para o Planeamento da Fase A

| Decisão | Impacto dos dados |
|---|---|
| `UNIQUE (tenant_id, nuit)` em `third_parties` | **Pode entrar na migração sem backfill prévio** — não há conflitos existentes |
| Backfill de `clients.third_party_id` | **Simples** — todos os clients têm NUIT, nenhum tem duplicado |
| Migração fase única vs. paralela em permanência | **Fase única é viável** — não há dados sujos que justifiquem complexidade adicional |
| Tamanho dos lotes de backfill | Recomendado: lotes de 500 com `BEGIN/COMMIT` individual — 2 213 registos cabem em 5 lotes |
| Janela de manutenção necessária | **Não** — a migração é additive; as tabelas existentes ficam intactas durante o backfill |

---

## Resposta à Pergunta 2 do Design

> "Fase única ou tabelas paralelas em permanência com vistas?"

**Fase única.** Os dados não têm sujidade que justifique complexidade adicional. Paralelismo permanente seria dívida técnica sem benefício de segurança — os dados já são limpos. O backfill de 2 213 registos é mecânico e seguro.
