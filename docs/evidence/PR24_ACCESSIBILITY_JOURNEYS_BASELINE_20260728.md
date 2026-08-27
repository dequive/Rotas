# PR-24 — Baseline de Acessibilidade e Jornadas

Data da evidência: 2026-07-28  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations

## Resultado

Foi criada uma baseline automatizada WCAG 2.2 A/AA para Manager e Driver, com
validação estática, teclado, axe e jornadas locais contra FastAPI/PostgreSQL.
Esta evidência não constitui certificação WCAG: auditoria manual com
tecnologias assistivas, dispositivos reais, todas as rotas e o SHA do release
candidate continuam pendentes.

## Implementado

- idioma do documento definido como `pt-MZ`;
- skip link visível ao foco para `#main-content`;
- um único landmark `main` no layout autenticado, removendo `main` aninhado na
  vertical Oficina;
- foco global e `prefers-reduced-motion` preservados;
- abas de OS e detalhe da viatura com `tablist`, `tab`, `tabpanel`, roving
  `tabIndex`, relações ARIA e teclas Left/Right/Home/End;
- tabelas horizontalmente scrollable têm região nomeada e foco de teclado;
- campo de pareamento Driver tem label, ajuda, estado inválido e erro live;
- drawer Hub 360 migrou para Radix Sheet com nome, descrição, focus trap,
  Escape e restauração de foco;
- contraste da Torre de Controlo corrigido;
- links de detalhe/histórico de viatura cumprem target mínimo automatizado;
- documentos de billing passam a consumir o contrato paginado `{items,total}`,
  eliminando crash SSR de `/cobranca`;
- scorecard não tenta ler métricas ausentes quando o backend retorna
  `tier=insuficiente`;
- seed E2E idempotente inclui uma viatura e um motorista exclusivamente
  sintéticos, removendo skips nas jornadas de detalhe;
- `@axe-core/playwright` integrado no E2E e gate de source integrado no CI.

## Defeitos encontrados pelo runtime

O primeiro axe falhou por:

1. dois contrastes insuficientes na Torre de Controlo;
2. regiões de tabela sem acesso por teclado;
3. links de viatura com target de 16 px.

O E2E funcional encontrou:

1. crash SSR em `/cobranca` por tratar resposta paginada como array;
2. crash do scorecard com `metrics={}` para dados insuficientes;
3. teste de viatura a seleccionar o QR code em vez de `Ver Detalhe`;
4. teste de motorista que fazia skip porque o produto usa Hub 360, não rota de
   detalhe.

Os defeitos foram corrigidos no produto/contrato e os mesmos gates repetidos.

## Evidência local final

```text
Accessibility source scan: 167 TSX, zero violações
Accessibility gate tests: 2 passed
Manager Vitest: 19 ficheiros, 89 passed
Manager typecheck: green
Manager Playwright: 17 passed, zero skipped
  axe A/AA: Torre, Oficina, OS, Viaturas e Motoristas
  teclado: skip link e widgets de abas
  funcional: auth, cobrança, frota e Hub 360
Manager build: 72 rotas, green
Driver Vitest: 26 passed
Driver typecheck: green
Driver build: 1.808 módulos + 93 módulos SW, green
Backend E2E seed: 1 passed
Backend Ruff seed: green
Backend Pyright integral: 0 erros, 0 warnings
Design System/no-demo/BFF: green
```

O build Driver precisou de repetição fora do sandbox por `Access is denied` do
reparse point OneDrive. O build Manager precisou remover um único directório
gerado e read-only em `.next/static` após o servidor dev deixar um lock; o
build recriado terminou verde.

## Supply chain

Adicionar axe não fechou PR-18. A auditoria actual continua:

- produção: 4 `high`;
- grafo completo: 17 `high` e 1 `moderate`.

Não foi executado `npm audit fix --force`.

## Critérios ainda pendentes

- auditoria manual WCAG 2.2 AA por especialista independente;
- NVDA/Firefox ou Chrome, JAWS quando aplicável, VoiceOver/Safari e TalkBack;
- teclado integral sem rato, ordem de foco, focus not obscured e modais;
- zoom 200%, reflow 400%, orientação, forced colors e contraste manual;
- mobile/touch real e uso com uma mão no Driver;
- linguagem, erros, instruções, autenticação acessível e conteúdo dinâmico;
- regressão visual e todas as 72 rotas, estados e papéis;
- jornadas completas com dois tenants e dados sobrepostos;
- reprodução no CI remoto e no SHA/digests do RC;
- sign-off PO, utilizadores e auditor independente.

Assim, PR-24 passa de `pending` para `in_progress`. G4 permanece vermelho e o
estado global permanece `NO-GO`.

