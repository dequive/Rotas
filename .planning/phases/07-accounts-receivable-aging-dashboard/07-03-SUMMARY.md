---
phase: 07
plan: 03
status: done
completed: 2026-06-21
---

# 07-03 SUMMARY — AR Dashboard Frontend

## What shipped

`apps/manager/app/ar/page.tsx` — Server Component AR dashboard:
- `as_of` date picker (HTML GET form, no client JS required)
- 3 KPI cards: Total em Aberto, Vencido (+30 d), Clientes com Dívida
- 5-bucket aging grid with color coding (slate=current/1-30, amber=31-60, red=61-90/+90)
- Top debtors table: client name + outstanding MZN + worst-bucket badge with colored dot + "Ver cliente" link

`apps/manager/app/components/SidebarLayout.tsx`:
- "Contas a Receber" entry at `key: "ar"` under Financeiro section, `href: "/ar"`

## Result

UI implemented. tsc clean (no type errors).
