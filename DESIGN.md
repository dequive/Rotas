# Design System — ROTAS

## Product Context

- **What this is:** Plataforma SaaS de gestão de frotas para transportadoras e operadores logísticos em Moçambique
- **Who it's for:** Gestores de frota e despachantes que controlam viagens, viaturas, motoristas, combustível e faturação diariamente
- **Space/industry:** Fleet management / logistics SaaS — B2B operacional
- **Project type:** Web app / dashboard (manager) + PWA mobile (driver)
- **Memorable quality:** Software sério para trabalho sério — sente-se como um cockpit, não um dashboard de startup

## Aesthetic Direction

- **Direction:** Industrial / Command Center
- **Decoration level:** Mínima — tipografia e dados fazem o trabalho. Sem blobs, gradientes decorativos, ou ilustrações
- **Mood:** Ferramenta de precisão. O utilizador abre e sente controlo antes de ler uma palavra. Como o que a Linear fez para developer tools — mas para operações logísticas em África
- **Why amber:** Toda a concorrência (Samsara, Fleetio, Motive) usa azul/verde + branco e parece igual. O acento âmbar evoca painéis de instrumentos, urgência operacional e valor monetário

## Typography

- **Display / H1:** Manrope 700–800 — geométrica, desenhada para ecrã, autoridade sem rigidez
- **Body / UI / Labels:** Manrope 400–600 — excelente legibilidade a 12–14px em tabelas densas
- **Data / IDs / Monetary:** IBM Plex Mono 400–500 — tabular nums perfeitos para valores MZN, matrículas (MQ-42-AB), IDs de viagem
- **Code:** IBM Plex Mono

### Loading (Google Fonts)
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Scale

| Token      | Size  | Weight | Usage                          |
|------------|-------|--------|--------------------------------|
| `text-2xl` | 28px  | 700    | Page titles (H1)               |
| `text-xl`  | 20px  | 700    | Section headings (H2)          |
| `text-lg`  | 18px  | 600    | Card titles, modal headers     |
| `text-base`| 14px  | 400    | Body, table rows               |
| `text-sm`  | 13px  | 400–500| Secondary info, descriptions   |
| `text-xs`  | 11px  | 600    | Labels, column headers (UC)    |
| `mono-xl`  | 26px  | 500    | KPI values (IBM Plex Mono)     |
| `mono-base`| 13px  | 400    | Plate numbers, IDs (IBM Plex Mono) |

## Color

- **Approach:** Restrained — 1 acento âmbar + neutrals. Cor é rara e significativa.
- **Rule:** Nunca usar gradientes decorativos.

### Token CSS — fonte única de verdade (`apps/manager/app/globals.css`)

Todos os valores vivem no bloco `:root`. Nenhum hex é permitido fora deste bloco.

```css
:root {
  /* ── Sidebar ──────────────────────────────── */
  --sidebar-bg:           #0f1623;
  --sidebar-hover:        #1e2d3d;
  --sidebar-active:       #1e3a52;
  --sidebar-text:         #94a3b8;
  --sidebar-text-active:  #f1f5f9;
  --sidebar-section:      #475569;

  /* ── Content surfaces ─────────────────────── */
  --bg:           #f1f5f9;
  --surface:      #ffffff;
  --surface-2:    #f8fafc;
  --border-color: #e2e8f0;
  --border-strong:#cbd5e1;

  /* ── Text ─────────────────────────────────── */
  --ink:          #0f172a;
  --ink-2:        #334155;
  --muted-color:  #64748b;
  --placeholder:  #94a3b8;

  /* ── Accent — amber (primary) ─────────────── */
  --amber:        #f59e0b;
  --amber-light:  #fef3c7;
  --amber-dark:   #d97706;

  /* ── Accent — blue (secondary) ────────────── */
  --blue:         #2563eb;
  --blue-light:   #eff6ff;
  --blue-dark:    #1d4ed8;
  --blue-border:  #bfdbfe;

  /* ── Semantic ─────────────────────────────── */
  --success:        #16a34a;
  --success-bg:     #f0fdf4;
  --success-border: #b7e1c8;
  --warning:        #d97706;
  --warning-bg:     #fffbeb;
  --warning-border: #f4d292;
  --error:          #dc2626;
  --error-bg:       #fef2f2;
  --error-border:   #fca5a5;
  --info:           #0891b2;
  --info-bg:        #ecfeff;
  --info-border:    #a5f3fc;

  /* ── Spacing scale ────────────────────────── */
  --s1:  4px;
  --s2:  8px;
  --s3:  12px;
  --s4:  16px;
  --s5:  20px;
  --s6:  24px;
  --s7:  32px;
  --s8:  48px;

  /* ── Border radius ────────────────────────── */
  --r-sm:  4px;
  --r-md:  6px;
  --r-lg:  8px;
  --r-xl:  12px;

  /* ── Elevation ────────────────────────────── */
  --shadow-sm: 0 1px 3px rgba(15,23,42,.08), 0 1px 2px rgba(15,23,42,.04);
  --shadow-md: 0 4px 12px rgba(15,23,42,.10), 0 2px 4px rgba(15,23,42,.06);

  /* ── Semantic borders ─────────────────────── */
  /* (ver acima — cada cor semântica tem --*-border par) */

  /* ── Track / fill surface ─────────────────── */
  --track: #edf2f7;

  /* ── Transitions ──────────────────────────── */
  --transition-fast:   80ms ease-out;
  --transition-base:  100ms ease-out;
  --transition-modal: 150ms ease-out;
}
```

### Regras de uso

| Token | Uso |
|-------|-----|
| `--amber` | Botão primário, KPI de receita, left-border do item activo na sidebar |
| `--amber-dark` | Hover de botão primário |
| `--amber-light` | Background de badge/icon âmbar |
| `--blue` | Links, estados activos em tabelas, estados secundários |
| `--blue-light` | Background de badges/icons azuis |
| `--blue-border` | Borda de callouts informativos (autofill-summary, module-state) |
| `--success` | Estado "Em Rota", métricas positivas |
| `--warning` | Estados de pausa/atenção, ícones de compliance |
| `--error` | Erros críticos, alertas, combustível baixo |
| `--info` | Estados informativos neutros |
| `--track` | Track de progress bars, fills subtis de fundo |
| `--surface` | Fundo de cards, modais, inputs, botões ghost |
| `--surface-2` | Hover de table rows, fundo de secções secundárias |
| `--bg` | Fundo da página |
| `--muted-color` | Texto secundário, labels, placeholders |
| `--border-color` | Divisórias, bordas de cards e inputs |
| `--sidebar-bg` | Fundo da sidebar — também usado em painéis dark (tms-hero) |

**Proibido:**
- Nunca usar gradientes decorativos
- Nunca hardcode hex em CSS utility classes — apenas `var(--token)`
- Nunca purple — não pertence ao sistema
- Nunca azul/verde como cor primária de acção

### Tailwind mapping (`apps/manager/tailwind.config.ts`)

Cada token CSS tem uma utility Tailwind correspondente:

```
bg-amber          → var(--amber)
bg-amber-light    → var(--amber-light)
text-amber-dark   → var(--amber-dark)
bg-success-bg     → var(--success-bg)
border-success-border → var(--success-border)
bg-error-bg       → var(--error-bg)
border-error-border   → var(--error-border)
bg-warning-bg     → var(--warning-bg)
bg-blue-light     → var(--blue-light)
border-blue-border    → var(--blue-border)
bg-info-bg        → var(--info-bg)
bg-track          → var(--track)
bg-surface        → var(--surface)
bg-surface-2      → var(--surface-2)
text-ink          → var(--ink)
text-muted        → var(--muted-color)
shadow-design-sm  → var(--shadow-sm)
shadow-design-md  → var(--shadow-md)
```

## Spacing

- **Base unit:** 4px
- **Density:** Confortável — nem compacto, nem espaçoso

```
--s1:  4px    gap mínimo, separação interna
--s2:  8px    padding de badge, gap de ícone + label
--s3:  12px   padding de nav item, gap de secção
--s4:  16px   padding de card, gap de grid KPI
--s5:  20px   padding de topbar / tabela
--s6:  24px   padding de content area
--s7:  32px   gap entre secções
--s8:  48px   espaço de página, separadores maiores
```

Tailwind utilities: `p-s4`, `gap-s2`, `mt-s7`, etc.

## Layout

- **Shell:** `display: grid; grid-template-columns: 248px minmax(0, 1fr);`
- **Sidebar width:** 248px fixo (56px em modo colapsado)
- **Content area:** padding `--s6` (24px)
- **KPI grid:** `grid-template-columns: repeat(4, 1fr)`
- **Max content width:** 1440px
- **Table pattern:** card com header (título + count badge) + `<table>`

### Border radius

```
--r-sm:  4px   badges, chips
--r-md:  6px   botões, inputs, nav items
--r-lg:  8px   cards, table cards
--r-xl:  12px  modais, panels maiores
```

Tailwind utilities: `rounded-ds-sm`, `rounded-ds-md`, `rounded-ds-lg`, `rounded-ds-xl`

### Sidebar — estrutura obrigatória

```
Operações   → Torre de Controlo, Viagens, Despachos
Frota       → Viaturas, Motoristas, Manutenção, Terceiros
Financeiro  → Clientes, Contratos, Cobrança, Contas a Receber, Análise
Config      → Destinos, Alertas, Segurança, Definições
```

Nunca uma lista plana sem agrupamento. Item activo tem `border-l-2 border-amber`.

## Motion

- **Approach:** Mínimo-funcional — só transições que ajudam a compreensão
- Sidebar hover: `100ms ease-out`
- Modais open/close: `150ms ease-out`
- Table row hover: `80ms`
- Sem animações decorativas, scroll-driven effects, ou micro-animations de entrada

```css
--transition-fast:   80ms ease-out;
--transition-base:  100ms ease-out;
--transition-modal: 150ms ease-out;
```

## Components — Padrões canónicos

### Button (`apps/manager/app/components/ui/Button.tsx`)

Componente React — nunca instanciar estilos de botão directamente.

```tsx
<Button variant="primary">Guardar</Button>
<Button variant="secondary">Cancelar</Button>
<Button variant="ghost" size="sm">Filtrar</Button>
<Button variant="danger">Eliminar</Button>
<Button variant="primary" loading={saving}>Guardar</Button>
```

| Variante    | Background       | Texto        | Borda            | Hover             |
|-------------|------------------|--------------|------------------|-------------------|
| `primary`   | `--amber`        | `--ink`      | nenhuma          | `--amber-dark`    |
| `secondary` | `--surface`      | `--ink`      | `--border-color` | `--surface-2`     |
| `ghost`     | transparente     | `--ink`      | `--border-color` | `--surface-2`     |
| `danger`    | transparente     | `--error`    | `--error`        | `--error-bg`      |

Tamanhos: `sm` (h-8, text-xs) · `md` (h-[38px], text-sm — default)

### StatusBadge (`apps/manager/app/components/ui/StatusBadge.tsx`)

Componente React — sempre com dot `::before` colorido à esquerda.

```tsx
<StatusBadge status="em-rota" />
<StatusBadge status="paragem" />
<StatusBadge status="concluida" label="Entregue" />
```

| Status key      | Dot            | Background        | Texto           |
|-----------------|----------------|-------------------|-----------------|
| `em-rota`       | `--success`    | `--success-bg`    | `--success`     |
| `paragem`       | `--warning`    | `--warning-bg`    | `--warning`     |
| `descarga`      | `--amber`      | `--amber-light`   | `--amber-dark`  |
| `alerta`        | `--error`      | `--error-bg`      | `--error`       |
| `aguarda`       | `--info`       | `--info-bg`       | `--info`        |
| `in_progress`   | `--amber`      | `--amber-light`   | `--amber-dark`  |
| `concluida`     | `--success`    | `--success-bg`    | `--success`     |
| `cancelada`     | `--error`      | `--error-bg`      | `--error`       |

Nunca usar badges sem dot. Nunca instanciar a classe CSS `.badge` directamente — usar `<StatusBadge>`.

### KpiCard (`apps/manager/app/components/ui/KpiCard.tsx`)

```tsx
<KpiCard label="Receita" value="842.500 MZN" semantic="amber" />
<KpiCard label="Viagens" value={12} trend={{ direction: 'up', label: '+3 vs ontem', positiveIsUp: true }} />
<KpiCard label="Alertas" value={3} semantic="error" loading={false} />
```

- Fundo `--surface`, borda `--border-color`, shadow `--shadow-sm`
- Label: 11px 600 uppercase `--muted-color`
- Valor: IBM Plex Mono 26px 500 `--ink` (ou cor semântica via `semantic` prop)
- Trend: 11px com seta ↑/↓, verde se positivo, vermelho se negativo

### Tabelas

- Header row: fundo `--surface-2`, 11px 600 uppercase `--muted-color`
- Body rows: hover `--surface-2`, `border-bottom: 1px solid --border-color`
- Matrículas e IDs: IBM Plex Mono 12px
- Nomes: Manrope 500 `--ink`
- Coluna de acções: `position: sticky; right: 0` com shadow de separação

### Inputs e formulários

```css
/* estado normal */
border: 1px solid var(--border-color);
background: var(--surface);

/* focus */
border-color: var(--amber);
box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.12);

/* erro */
border-color: var(--error);
```

### Modais

- `border-radius: var(--r-xl)` (12px)
- `padding: var(--s6)` (24px)
- Backdrop: `rgba(15, 23, 42, 0.45)`
- Header: título 18px + botão fechar
- Actions footer: `border-top: 1px solid var(--border-color)`

### Badges de ícone (icon pills)

Usados em history markers, queue icons, metric icons:

| Classe           | Background         | Cor do ícone  |
|------------------|--------------------|---------------|
| `.*.red / error` | `--error-bg`       | `--error`     |
| `.*.orange / warning` | `--warning-bg` | `--warning`  |
| `.*.blue`        | `--blue-light`     | `--blue`      |
| `.*.info`        | `--info-bg`        | `--info`      |
| `.*.green / success` | `--success-bg` | `--success`  |
| `.*.amber`       | `--amber-light`    | `--amber-dark`|

Nunca `.*.purple` — não existe no sistema.

### Data source indicators

```css
.data-source.api      { background: --success-bg; border-color: --success-border; color: --success; }
.data-source.fallback { background: --warning-bg; border-color: --warning-border; color: --warning; }
```

## Arquitectura de estilos — cascata obrigatória

```
:root (globals.css)          ← única fonte de valores
      ↓
tailwind.config.ts           ← mapeia cada token para utility class
      ↓
globals.css utility classes  ← apenas var(--token), ZERO hex
      ↓
React components (ui/)       ← apenas Tailwind classes
      ↓
Pages & feature components   ← consomem componentes, nunca estilos directos
```

**Regras de enforcement:**
1. Nenhum hex fora do bloco `:root` — verificável via script
2. Nenhuma cor hardcoded em componentes React — apenas classes Tailwind mapeadas para tokens
3. Novos componentes UI → criar em `apps/manager/app/components/ui/`
4. Novos tokens → adicionar a `:root`, depois ao `tailwind.config.ts`
5. Nunca usar aliases legados (`--line`, `--panel`, `--muted`, `--red`, etc.) em código novo

## Decisions Log

| Data       | Decisão                                         | Racional                                                                |
|------------|-------------------------------------------------|-------------------------------------------------------------------------|
| 2026-06-06 | Acento âmbar em vez de azul/verde               | Toda a concorrência usa azul/verde; âmbar diferencia e evoca cockpit    |
| 2026-06-06 | Manrope como fonte principal                    | Geométrica, não overused, excelente a tamanhos pequenos                 |
| 2026-06-06 | IBM Plex Mono para dados/IDs                    | Tabular nums, distingue 0/O e 1/l/I, desenhada para software            |
| 2026-06-06 | Sidebar com secções agrupadas                   | Escalável, orienta o utilizador, evita lista plana                      |
| 2026-06-06 | Decoração mínima                                | Produto operacional — dados fazem o trabalho                            |
| 2026-06-20 | Botão primário migrado de azul para âmbar       | Correcção de violação — blue primary quebrava brand identity            |
| 2026-06-20 | Componente Button.tsx canónico                  | Substitui `.primary-btn`/`.login-btn` — variantes primary/secondary/ghost/danger |
| 2026-06-20 | Tokens de borda semânticos (`--*-border`)       | Elimina hex hardcoded em borders de badges, callouts e alerts           |
| 2026-06-20 | Token `--track` para progress bars              | Valor de fill consistente vs improviso por componente                   |
| 2026-06-20 | Migração completa de aliases legados            | `--line`, `--panel`, `--muted`, `--red`, etc. → nomes canónicos         |
| 2026-06-20 | Zero hex fora de `:root` (verificado por script)| Arquitectura de token enforçada — dark mode e theming possíveis no futuro |
