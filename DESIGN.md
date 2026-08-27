# Design System ROTAS — Oficina Auto

**Versão 1.3.1 · Autoridade visual e de interação do frontend**
Escopo: Manager Next.js + Driver PWA

## 1. Princípios

O ROTAS é software operacional B2B. A interface deve transmitir controlo,
clareza e confiança sem decoração gratuita. Toda decisão visual deve melhorar
leitura, decisão ou execução de uma tarefa.

- Mobile-first para mecânicos e motoristas.
- Desktop eficiente para gestores e operadores.
- Cor nunca é o único portador de significado.
- Evidências e documentos aprovados são visualmente imutáveis.
- Um único botão `accent` por ecrã.
- Alvos de toque têm pelo menos 44 × 44 px em dispositivos de toque.
- Movimento é funcional, curto e removido quando `prefers-reduced-motion` está ativo.
- Hexadecimais vivem apenas nos blocos `:root` e `.dark` de `app/globals.css`.
- Nunca instanciar a classe CSS `.badge` diretamente; usar sempre `<StatusBadge>`.
- Badges exigem ícone e texto. Dot é permitido apenas em variantes compactas.

## 2. Tipografia

- UI e texto: `Inter`, fallback `system-ui, sans-serif`.
- Matrículas, códigos, IDs e valores: `JetBrains Mono`, fallback
  `ui-monospace, monospace`.
- Valores monetários usam `font-variant-numeric: tabular-nums`.

Uma eventual migração para Manrope + IBM Plex Mono é uma onda visual separada
e não faz parte desta versão.

| Token | Tamanho | Peso | Line-height | Uso |
|---|---:|---:|---:|---|
| `display` | 32px | 700 | 1.2 | título principal |
| `h1` | 24px | 600 | 1.25 | título de secção |
| `h2` | 20px | 600 | 1.3 | título de card |
| `h3` | 16px | 600 | 1.4 | subtítulo |
| `body` | 14px | 400 | 1.5 | texto |
| `body-sm` | 13px | 400 | 1.45 | metadados |
| `caption` | 12px | 500 | 1.4 | badges e timestamps |

## 3. Cor

### Brand ROTAS

`rotas-500` (`#3B6B9C`) é a ação primária. A escala completa vai de
`rotas-50` a `rotas-950` e está declarada em `app/globals.css`.

### Accent

`accent-600` (`#C2410C`) é reservado para uma única ação especial por ecrã,
como criar orçamento suplementar. `accent-500` (`#EA580C`) é o hover.

### Estados da Oficina

| Estado | Token |
|---|---|
| Recepção | `status-reception` |
| Diagnóstico | `status-diagnosis` |
| Aguardando aprovação | `status-awaiting` |
| Orçamento adicional | `status-supplement` |
| Em execução | `status-execution` |
| Controlo de qualidade | `status-quality` |
| Entregue / faturado | `status-delivered` |
| Cancelado / recusado | `status-cancelled` |
| Rascunho | `status-draft` |

Cada estado possui variante sólida e `soft`. O roxo é permitido apenas para
`status-quality`.

Todos os pares de texto e controlo devem cumprir WCAG AA. A conformidade é um
gate de certificação F6 e só pode ser declarada após relatório automatizado e
revisão dos estados light/dark.

## 4. Espaçamento, forma e foco

- Escala base: 4, 8, 12, 16, 20, 24, 32, 40, 48 e 64 px.
- Radius: `sm` 6px, `md` 8px, `lg` 12px, `xl` 16px, `full` 9999px.
- Modais usam `border-radius: var(--r-xl)`.
- Sombras: `shadow-sm`, `shadow`, `shadow-md`, `shadow-lg` e `shadow-card`.
- Foco visível usa `--focus-ring` e, quando necessário, `--focus-ring-soft`.
- A decoração é mínima; gradientes decorativos e blobs são proibidos.

## 5. Componentes canónicos

### Button

Variantes: `primary`, `secondary`, `accent`, `ghost` e `destructive`.
Tamanhos visuais: `sm` 32px, `md` 40px e `lg` 48px. Em dispositivos de toque,
o alvo interativo é elevado a pelo menos 44px.

### StatusBadge

```tsx
<StatusBadge status="awaiting" variant="solid" size="sm" />
```

Props: `status`, `variant="solid|soft"`, `size="sm|md"` e
`icon?: LucideIcon` para substituir o ícone semântico predefinido. Ícone e texto
são obrigatórios, exceto numa futura variante compacta explicitamente tipada.
Nunca usar a classe CSS `.badge` diretamente.

### KpiCard

```tsx
<KpiCard label="Receita" value="842.500 MZN" semantic="accent" />
```

`semantic="accent"` é a API canónica. `amber` pode existir apenas como alias
temporário para código legado.

### OsCard

Inclui foto 48 × 48, matrícula mono, cliente, técnico, valor acumulado, estado
principal e sinal de orçamento adicional. Suplemento pendente adiciona borda
esquerda sem alterar o estado principal.

### Tabelas

Cabeçalhos são discretos, ações ficam acessíveis e valores/IDs usam números
tabulares. No mobile, tabelas densas transformam-se em cards ou permitem scroll
explícito; nunca comprimem colunas até perder legibilidade.

### Inputs e formulários

- Normal: borda `--border-color` e fundo `--surface`.
- Foco: `--focus-ring`/`--focus-ring-soft`.
- Erro: tokens semânticos de erro.
- `rgba(...)` direto e alias `--amber` são proibidos no foco.

### Icon pills

As variantes permitidas são `.error`, `.warning`, `.info` e `.success`.
`.blue`, `.amber`, `.purple` e tokens de paleta são proibidos em código novo.

### Indicadores de fonte de dados

Estados canónicos: `api`, `cache`, `degraded` e `unavailable`.

- `api`: fonte operacional em tempo real.
- `cache`: fonte operacional válida, com idade declarada.
- `degraded`: dados reais parciais ou desatualizados, sempre identificados.
- `unavailable`: nenhum dado operacional disponível; apresentar erro/empty state.
- `fallback` é proibido porque pode sugerir autorização para dados fictícios.

### Evidências e documentos

Timelines são append-only. Orçamentos aprovados não oferecem edição; a única
ação de alteração comercial é criar um orçamento suplementar independente.

## 6. Fluxos vinculativos da Oficina

O frontend representa, sem inventar estados, a máquina de estados canónica:

`RECEBIDO → EM_DIAGNOSTICO → DIAGNOSTICO_CONCLUIDO → AGUARDANDO_APROVACAO → APROVADO → EM_EXECUCAO → EXECUCAO_CONCLUIDA → QC_CONCLUIDO → FATURADO → ENTREGUE`

- Suplementos têm aprovação própria.
- Reserva lógica de peça não equivale a consumo físico.
- Faturação exige controlo de qualidade e gera documento imutável.
- Entrega exige QC e condição financeira válida.
- Override financeiro só pode ser exposto após existir contrato de API, RBAC e
  auditoria certificados; o frontend atual não o simula.
- Analytics é derivado e nunca escreve diretamente no núcleo transacional.

## 7. Arquitetura de estilos

```text
:root + .dark em app/globals.css  ← única fonte de valores hex
        ↓
tailwind.config.ts
        ↓
globals.css utilities            ← apenas var(--token)
        ↓
components/ui                    ← primitivos reutilizáveis
        ↓
oficina/components               ← compostos de domínio
        ↓
features e páginas
```

Regras de enforcement:

1. Hex apenas em `:root` e `.dark`.
2. Nenhuma cor hardcoded em componentes React.
3. Primitivos reutilizáveis vivem em `components/ui`.
4. Componentes compostos da Oficina vivem em `oficina/components`.
5. Código novo nunca consome aliases legados.
6. Dark mode resulta dos mesmos tokens.
7. Loading, vazio, erro, sem permissão e dados parciais são estados obrigatórios.
8. Mutações usam BFF/API real, RBAC, auditoria e `Idempotency-Key` quando o
   contrato da operação o suporta.

## 8. Gates de qualidade

- TypeScript sem erros.
- Testes unitários dos componentes e estados.
- Build de produção.
- Navegação por teclado e foco visível.
- WCAG AA certificado.
- Responsivo em 360px, 768px, 1280px e 1440px.
- Nenhum dado de demonstração em jornadas reais.
- Ações mutáveis usam BFF/API real, RBAC e auditoria.
- Idempotência verificada como gate de implementação progressiva.

O plano de migração e os gates por onda estão em
`docs/FRONTEND_REFOUNDATION_PLAN.md`.
