---
phase: quick-260621-uvf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/260621-uvf-REPORT.md
autonomous: true
requirements: [UVF-AUDIT-01]

must_haves:
  truths:
    - "Todos os 4 queries SQL executaram contra PostgreSQL porta 55432 sem erro"
    - "Os resultados estão registados em REPORT.md com números concretos"
    - "O risco da Fase A é classificado como Médio ou Alto com justificação baseada nos dados"
  artifacts:
    - path: ".planning/quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/260621-uvf-REPORT.md"
      provides: "Resultados das 4 queries + classificação de risco"
      contains: "volume, nuit_nulo, nuit_ok, duplicados, sobreposição, risco"
  key_links:
    - from: "PostgreSQL localhost:55432/rotas"
      to: "260621-uvf-REPORT.md"
      via: "psql queries diretas"
      pattern: "SELECT.*clients.*third_parties"
---

<objective>
Fase 0 — auditoria de dados: executar 4 queries SQL de diagnóstico contra a base de dados PostgreSQL
(porta 55432) para dimensionar a migração clients → third_parties. Sem alterações de schema.

Purpose: Antes de planear a Fase A (migração clients → third_parties), é necessário conhecer os números
reais — volume de registos, qualidade do campo nuit, duplicados por tenant, e sobreposição já existente
entre clients e third_parties. Esses números determinam se a migração é de risco Médio ou Alto.

Output: REPORT.md com resultados brutos de cada query + classificação de risco justificada.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Executar as 4 queries de auditoria e escrever REPORT.md</name>
  <files>.planning/quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/260621-uvf-REPORT.md</files>
  <action>
Executar as seguintes 4 queries SQL contra PostgreSQL (connection string:
postgresql://rotas:rotas@localhost:55432/rotas) via psql ou asyncpg/psycopg CLI.

Usar o comando psql desta forma para cada query:
  psql postgresql://rotas:rotas@localhost:55432/rotas -c "<QUERY>"

**Query 1 — Volume de registos:**
```sql
SELECT 'clients' AS tabela, count(*) AS total FROM clients
UNION ALL
SELECT 'third_parties', count(*) FROM third_parties;
```

**Query 2 — Qualidade do NUIT em clients:**
```sql
SELECT
  count(*) FILTER (WHERE nuit IS NULL)     AS nuit_nulo,
  count(*) FILTER (WHERE nuit IS NOT NULL) AS nuit_ok
FROM clients;
```

**Query 3 — NUITs duplicados por tenant em clients:**
```sql
SELECT tenant_id, nuit, count(*) AS n
FROM clients
WHERE nuit IS NOT NULL
GROUP BY tenant_id, nuit
HAVING count(*) > 1
ORDER BY n DESC;
```

**Query 4 — Sobreposição real clients ∩ third_parties por NUIT:**
```sql
SELECT count(*) AS ja_sobrepostos
FROM clients c
JOIN third_parties tp
  ON tp.tenant_id = c.tenant_id
 AND tp.nuit = c.nuit
WHERE c.nuit IS NOT NULL;
```

Recolher os resultados de todas as 4 queries. Se o psql não estiver disponível no PATH, usar
`python -c "import asyncio, asyncpg; ..."` com asyncpg já instalado no backend/.venv, ou usar
`python -m psycopg` com psycopg[binary] disponível.

Com base nos resultados, aplicar as seguintes regras de classificação de risco:

**Risco ALTO se qualquer condição for verdadeira:**
- Query 3 retorna >= 1 linha (existem NUITs duplicados por tenant — colisão na chave única)
- Query 4 retorna ja_sobrepostos > 0 (registos já existem em ambas as tabelas — conflito de PK/NUIT)
- Query 2: nuit_nulo > 50% do total de clients (migração vai criar third_parties sem NUIT, inutilizáveis
  para a UNION ALL na party directory)

**Risco MÉDIO se todas as condições forem verdadeiras:**
- Query 3: zero linhas (sem duplicados)
- Query 4: ja_sobrepostos = 0 (sem sobreposição)
- Query 2: nuit_ok >= 50% dos clients

Escrever o ficheiro REPORT.md com a estrutura definida no bloco `<done>`.
  </action>
  <verify>
    <automated>Test-Path "C:\Users\Quive\OneDrive\Documents\Rotas\.planning\quick\260621-uvf-fase-0-auditoria-dados-clients-third-par\260621-uvf-REPORT.md"</automated>
  </verify>
  <done>
REPORT.md existe e contém:

1. Resultados brutos de cada uma das 4 queries (números exactos, não estimativas)
2. Classificação de risco: **MÉDIO** ou **ALTO** (uma linha clara no topo do relatório)
3. Justificação: quais condições foram activadas ou não (máximo 3 frases)

Estrutura do ficheiro:

```markdown
# Fase 0 — Auditoria de Dados: clients → third_parties

**Data:** 2026-06-21
**Classificação de Risco Fase A:** [MÉDIO | ALTO]

## Justificação

[Máx. 3 frases explicando quais condições determinaram a classificação]

## Query 1 — Volume

| tabela | total |
|--------|-------|
| clients | X |
| third_parties | X |

## Query 2 — Qualidade do NUIT em clients

| nuit_nulo | nuit_ok |
|-----------|---------|
| X | X |

## Query 3 — NUITs Duplicados por Tenant

[Tabela com resultados, ou "Nenhum duplicado encontrado." se zero linhas]

## Query 4 — Sobreposição clients ∩ third_parties

| ja_sobrepostos |
|----------------|
| X |

## Implicações para a Fase A

[Bullet list de 2-4 pontos sobre o que os números implicam para o planeamento da migração]
```
  </done>
</task>

</tasks>

<verification>
Confirmar que REPORT.md foi escrito com resultados reais (não placeholders) e contém uma
classificação de risco explícita no topo. Verificar que os números das queries são coerentes
(ex: nuit_nulo + nuit_ok deve igualar o total de clients da Query 1).
</verification>

<success_criteria>
- REPORT.md existe em .planning/quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/
- Contém resultados de todas as 4 queries com números reais da BD
- Classificação de risco (MÉDIO/ALTO) declarada com justificação
- Nenhuma alteração feita à BD — apenas leitura (SELECT only)
</success_criteria>

<output>
Após conclusão, criar `.planning/quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/260621-uvf-SUMMARY.md`
com o resultado da auditoria e a classificação de risco para referência futura no planeamento da migração.
</output>
