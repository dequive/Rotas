# Phase 2: PWA Offline-First Completion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 02-pwa-offline-first-completion
**Areas discussed:** Offline feedback UI, Expiração de sessão do motorista, Visibilidade da fila de sync, Branding do manifest

---

## Offline feedback UI

| Option | Description | Selected |
|--------|-------------|----------|
| Banner persistente no topo | Barra colorida fixada no topo da app enquanto offline. Desaparece quando volta a conexão. | ✓ |
| Toast ao mudar de estado | Toast "Sem ligação" quando offline, toast "Online" quando volta. | |
| Indicador no canto (icon) | Ícone de WiFi cortado no canto superior direito. | |
| Sem indicador visual | App funciona silenciosamente. | |

**User's choice:** Banner persistente no topo
**Notes:** Preferência por feedback claro e não disruptivo — o banner é óbvio mas não interrompe o fluxo de trabalho.

---

**Q: Quando volta online e sync começa, o que vê?**

| Option | Description | Selected |
|--------|-------------|----------|
| Banner muda para verde com "A sincronizar..." | Feedback claro do processo completo. | ✓ |
| Toast "Online — X registos sincronizados" | Só aparece no fim. | |
| Nada — banner simplesmente desaparece | Online = banner some. | |

**User's choice:** Banner muda para verde com "A sincronizar..."

---

**Q: Botão "Verificar atualizações" — onde fica?**

| Option | Description | Selected |
|--------|-------------|----------|
| No menu / configurações da app | Escondido num menu. | |
| No banner offline quando online | Aparece no banner quando nova versão disponível. Contextual. | ✓ |
| Sempre visível no dashboard | Botão permanente. | |

**User's choice:** No banner quando nova versão disponível

---

## Expiração de sessão do motorista

| Option | Description | Selected |
|--------|-------------|----------|
| Bloquear sync, preservar dados locais | "Sessão expirada — contacta o gestor para re-parear". App continua offline. | ✓ |
| Logout forçado imediato | App apaga tudo e volta ao ecrã de pareamento. | |
| Retry silencioso infinito | Continua a tentar sem avisar. | |

**User's choice:** Bloquear sync, preservar dados locais
**Notes:** Dados financeiros não podem ser perdidos.

---

**Q: Acesso às funcionalidades offline com sessão expirada?**

| Option | Description | Selected |
|--------|-------------|----------|
| Sim — app totalmente funcional offline, só sync bloqueada | Motorista continua a registar. Sync reativa após re-parear. | ✓ |
| Não — funcionalidades de escrita bloqueadas | Só pode ver viagens anteriores. | |

**User's choice:** Sim — app totalmente funcional offline

---

**Q: Revogação de acesso (motorista desativado pelo gestor) — surgiu como resposta livre**

**User's comment:** "Se o motorista for desligado da empresa, deve perder o acesso"

| Option | Description | Selected |
|--------|-------------|----------|
| Revogar imediatamente via backend (401 na próxima sync) | driver_session invalidada → 401 → "acesso revogado". | ✓ |
| Expirar naturalmente | Token continua válido até ao TTL. | |

**User's choice:** Revogar imediatamente via backend

---

**Q: Dados locais não sincronizados após revogação?**

| Option | Description | Selected |
|--------|-------------|----------|
| Preservar dados e mostrar aviso | "Acesso revogado. Os teus registos locais foram preservados." | ✓ |
| Apagar dados locais imediatamente | Limpa Dexie e volta ao ecrã inicial. | |

**User's choice:** Preservar dados e mostrar aviso

---

## Visibilidade da fila de sync

| Option | Description | Selected |
|--------|-------------|----------|
| Contador no banner de estado | "X registos pendentes" no banner. Reutiliza componente. | ✓ |
| Só quando há erros | Indicador só quando itens falharam repetidamente. | |
| Sempre visível na dashboard | Contador permanente na dashboard. | |

**User's choice:** Contador no banner de estado

---

**Q: Quando items falham repetidamente?**

| Option | Description | Selected |
|--------|-------------|----------|
| Alerta no banner com "X registos com erro" | Banner muda de cor (vermelho). | ✓ |
| Silencioso — continua a tentar em background | Retry automático sem avisar. | |
| Modal de erro com detalhes do item | Pop-up com item que falhou. | |

**User's choice:** Alerta no banner com "X registos com erro"

---

## Branding do manifest (PWA-02)

**Q: Nome completo e nome curto?**

| Option | Description | Selected |
|--------|-------------|----------|
| ROTAS / ROTAS | Nome simples. | |
| ROTAS Frota / ROTAS | Nome descritivo. | |
| ROTAS Motorista / Motorista | Diferencia do app do gestor. | ✓ |

**User's choice:** ROTAS Motorista / Motorista

---

**Q: theme_color?**

| Option | Description | Selected |
|--------|-------------|----------|
| Azul escuro profissional (#1e3a5f) | Cor corporativa séria. | |
| Laranja operações (#f97316) | Energético, visível. | |
| Verde sucesso (#16a34a) | Associado a OK, sincronizado. | |
| Você decide a cor | Claude escolhe baseado no App.tsx | ✓ |

**User's choice:** Claude decide (→ #102033 baseado em --nav do CSS existente)

---

**Q: Ícones do manifest?**

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder simples com letra R | SVG com "R" em fundo colorido. Rápido. | ✓ |
| Forneço os ficheiros manualmente | Plano espera por PNGs externos. | |
| Script de geração automática | Script Node.js para gerar ícones. | |

**User's choice:** Placeholder simples com letra R

---

## Claude's Discretion

- Paleta exata de cores do banner (dentro dos CSS vars existentes)
- Animação/transição do banner
- Estrutura interna do componente de banner (hook + componente)
- Estratégia de retry do Workbox
- Formato do SVG placeholder dos ícones
- `theme_color` → #102033 (--nav do CSS existente)

## Deferred Ideas

- Interface de resolução de conflitos para motorista — v2
- Scorecard de motoristas — v2
- Notificações push quando sync falha — fora do escopo
