# Design System — ROTAS

## Product Context
- **What this is:** Plataforma SaaS de gestão de frotas para transportadoras e operadores logísticos em Moçambique
- **Who it's for:** Gestores de frota e despachantes que controlam viagens, viaturas, motoristas, combustível e faturação diariamente
- **Space/industry:** Fleet management / logistics SaaS — B2B operacional
- **Project type:** Web app / dashboard (manager) + PWA mobile (driver)
- **Memorable quality:** Software sério para trabalho sério — sente-se como um cockpit, não um dashboard de startup

## Aesthetic Direction
- **Direction:** Industrial / Command Center
- **Decoration level:** Mínima — tipografia e dados fazem o trabalho. Sem blobs, gradientes, ou ilustrações decorativas
- **Mood:** Ferramenta de precisão. O utilizador abre e sente controlo antes de ler uma palavra. Cada elemento justifica a sua presença. Como o que a Linear fez para developer tools — mas para operações logísticas em África
- **Why not blue/green like every other fleet tool:** Toda a concorrência (Samsara, Fleetio, Motive) usa azul/verde + branco e parece igual. O acento âmbar evoca painéis de instrumentos, urgência operacional e valor monetário — nenhum concorrente usa cores quentes

## Typography

- **Display / H1:** Manrope 700–800 — geométrica, desenhada para ecrã, autoridade sem rigidez
- **Body / UI / Labels:** Manrope 400–600 — excelente legibilidade a 12–14px em tabelas densas
- **Data / IDs / Monetary:** IBM Plex Mono 400–500 — desenhada pela IBM para software profissional; tabular nums perfeitos para valores MZN, matrículas (MQ-42-AB), IDs de viagem
- **Code:** IBM Plex Mono

### Loading (Google Fonts)
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Scale
| Token     | Size  | Weight | Usage                        |
|-----------|-------|--------|------------------------------|
| `text-2xl`| 28px  | 700    | Page titles (H1)             |
| `text-xl` | 20px  | 700    | Section headings (H2)        |
| `text-lg` | 18px  | 600    | Card titles, modal headers   |
| `text-base`| 14px | 400    | Body, table rows             |
| `text-sm` | 13px  | 400–500| Secondary info, descriptions |
| `text-xs` | 11px  | 600    | Labels, column headers (UC)  |
| `mono-xl` | 26px  | 500    | KPI values (IBM Plex Mono)   |
| `mono-base`| 13px | 400    | Plate numbers, IDs (IBM Plex Mono) |

## Color

- **Approach:** Restrained — 1 acento âmbar + neutrals. Cor é rara e significativa.

### Tokens CSS
```css
:root {
  /* Sidebar */
  --sidebar-bg:      #0f1623;
  --sidebar-hover:   #1e2d3d;
  --sidebar-active:  #1e3a52;
  --sidebar-text:    #94a3b8;
  --sidebar-text-active: #f1f5f9;
  --sidebar-section: #475569;

  /* Content surfaces */
  --bg:          #f1f5f9;
  --surface:     #ffffff;
  --surface-2:   #f8fafc;
  --border:      #e2e8f0;
  --border-strong: #cbd5e1;

  /* Text */
  --ink:         #0f172a;
  --ink-2:       #334155;
  --muted:       #64748b;
  --placeholder: #94a3b8;

  /* Accent — amber (primary) */
  --amber:       #f59e0b;
  --amber-light: #fef3c7;
  --amber-dark:  #d97706;

  /* Accent — blue (secondary: links, active states) */
  --blue:        #2563eb;
  --blue-light:  #eff6ff;
  --blue-dark:   #1d4ed8;

  /* Semantic */
  --success:     #16a34a;
  --success-bg:  #f0fdf4;
  --warning:     #d97706;
  --warning-bg:  #fffbeb;
  --error:       #dc2626;
  --error-bg:    #fef2f2;
  --info:        #0891b2;
  --info-bg:     #ecfeff;
}
```

### Usage rules
- **Âmbar** — brand mark, botão primário, KPI de receita, badge "Descarga", estados activos no sidebar. Nunca como cor de fundo em áreas grandes.
- **Azul** — links, estados "activo" em tabelas, focus ring secundário
- **Vermelho** — apenas erros e alertas críticos (combustível baixo, alerta pendente)
- **Verde** — estados "Em Rota", sucesso, métricas positivas
- Nunca usar gradientes decorativos

## Spacing

- **Base unit:** 4px
- **Density:** Confortável (não compacto, não espaçoso)

```
--s1:  4px   (gap mínimo, separação interna)
--s2:  8px   (padding de badge, gap de ícone+label)
--s3:  12px  (padding de nav item, gap de secção)
--s4:  16px  (padding de card, gap de grid KPI)
--s5:  20px  (padding de topbar/tabela)
--s6:  24px  (padding de content area)
--s7:  32px  (gap entre secções)
--s8:  48px  (espaço de página, separadores maiores)
```

## Layout

- **Approach:** Grid disciplinado
- **Shell:** `display: grid; grid-template-columns: 248px minmax(0, 1fr);`
- **Sidebar width:** 248px fixo
- **Content grid:** 12 colunas, gap 16px
- **Max content width:** 1440px
- **KPI pattern:** 4 cards no topo de cada página de dashboard (grid-template-columns: repeat(4, 1fr))
- **Table pattern:** card com header (título + count badge) + `<table>` standard

### Border radius
```
--r-sm:  4px   (badges, chips)
--r-md:  6px   (botões, inputs, nav items)
--r-lg:  8px   (cards, table cards)
--r-xl:  12px  (modais, panels maiores)
```

### Sidebar navigation — estrutura obrigatória
```
Operações   → Torre de Controlo, Viagens, Despachos
Frota       → Viaturas, Motoristas, Manutenção
Financeiro  → Contratos, Cobrança
Config      → Destinos, Utilizadores, Definições
```
Nunca uma lista plana de items sem agrupamento.

## Motion

- **Approach:** Mínimo-funcional — só transições que ajudam a compreensão
- Sidebar hover: `100ms ease-out`
- Modais open/close: `150ms ease-out`
- Table row hover: `80ms`
- Sem animações decorativas, sem scroll-driven effects, sem micro-animations de entrada

```css
--transition-fast:   80ms ease-out;
--transition-base:  100ms ease-out;
--transition-modal: 150ms ease-out;
```

## Components — Padrões obrigatórios

### Badges de estado
```
Em Rota    → badge-success  (verde)
Paragem    → badge-warning  (âmbar/laranja)
Descarga   → badge-amber    (âmbar claro)
Alerta     → badge-error    (vermelho)
Aguarda    → badge-info     (ciano)
```
Sempre com dot colorido à esquerda (`::before` circle). Nunca badges sem dot.

### KPI Cards
- Fundo `--surface`, border `--border`, shadow `--shadow-sm`
- Label: 11px 600 UC `--muted`
- Valor: IBM Plex Mono 26px 500 `--ink` (ou `--amber-dark` / `--error` quando semântico)
- Meta: 11px `--muted` com trend indicator (↑ verde / ↓ vermelho)

### Tabelas
- Header row: `--surface-2`, 11px 600 UC `--muted`, `--border-bottom`
- Body rows: hover `--surface-2`, border-bottom `--border`
- Plate numbers e IDs: IBM Plex Mono 12px
- Nomes de motoristas: Manrope 500 `--ink`

### Botões
```
Primary:  bg --amber,       color #0f1623,    hover --amber-dark
Ghost:    bg transparent,   border --border,  hover --surface-2
Danger:   bg transparent,   border --error,   color --error
```

### Inputs
- Border: `--border-strong`
- Focus: `border-color --amber` + `box-shadow 0 0 0 3px rgba(245,158,11,.12)`
- Error: `border-color --error`

## Decisions Log

| Data       | Decisão                                    | Racional                                                                  |
|------------|--------------------------------------------|---------------------------------------------------------------------------|
| 2026-06-06 | Acento âmbar em vez de azul/verde          | Toda a concorrência usa azul/verde; âmbar diferencia e evoca cockpit      |
| 2026-06-06 | Manrope como fonte principal               | Geométrica, desenhada para ecrã, não overused, excelente a tamanhos pequenos |
| 2026-06-06 | IBM Plex Mono para dados/IDs               | Tabular nums, desenhada para software profissional, distingue 0/O e 1/l/I |
| 2026-06-06 | Sidebar com secções agrupadas              | Escalável, orienta o utilizador, evita lista plana de 8 items             |
| 2026-06-06 | Decoração mínima                           | Produto operacional — dados fazem o trabalho, não ilustrações             |
| 2026-06-06 | Design system criado por /design-consultation | Baseado em pesquisa de Samsara/Fleetio + first-principles Moçambique      |
