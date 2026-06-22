---
plan: 11-05
status: done
---
# 11-05 SUMMARY — Manager UI

- `apps/manager/app/despacho/page.tsx` — server component with DespachoClient child
- `apps/manager/app/despacho/DespachoClient.tsx` — interactive table: Motorista | Veículo | Despacho | Custos | Saldo | Estado | Ações
- IBM Plex Mono on all MZN monetary values, Manrope for labels, amber (#f59e0b) accent on CTAs
- Balance coloring: green ≥ 0 (driver owes back), amber for minor shortfall, red for significant negative
- Badges with colored dot (::before pattern from DESIGN.md): amber=pending, green=approved, red=rejected
- "Emitir Despacho" opens modal → POST /trips/{id}/advance
- "Calcular Liquidação" → POST /trips/{id}/settlement
- "Aprovar" / "Rejeitar" inline actions
- "Download PDF" link for approved settlements
- "Despacho" link added to sidebar under Financeiro section with `Receipt` icon
