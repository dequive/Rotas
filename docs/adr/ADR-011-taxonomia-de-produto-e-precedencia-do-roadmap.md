# ADR-011: Taxonomia de produto e precedência do roadmap

## Status

Accepted

## Date

2026-08-23

## Context

Uma revisão adversarial do plano mestre confrontou a secção 3 com os domínios,
o substrato backend e a navegação Manager. A revisão confirmou quatro
ambiguidades estruturais:

- cobrança era atribuída simultaneamente a `Custos e Margem` e a
  `Clientes, Vendas e Cobrança`;
- Administração do Tenant e Administração SaaS eram separadas na taxonomia,
  mas fundidas no mesmo domínio;
- `Suporte Técnico-Operacional` aparecia como módulo vendável sem domínio
  próprio, embora concentre autenticação, ficheiros, auditoria e sync offline;
- a Oficina Intelligence Layer não declarava explicitamente que pertence ao
  domínio de Business Intelligence.

Também existiam duas ordens incompatíveis. A secção 9 colocava a fundação SaaS
na Wave 9, enquanto a secção 10 exigia isolamento tenant e entitlements antes
dos fluxos transacionais. A sequência C0-C4 e E0-E5 posteriormente adotada em
`AGENTS.md` já corrige a execução, mas o texto histórico não declarava essa
precedência.

No código atual, `product_modules` e a navegação distinguem apenas os bundles
legados `tms` e `oficina`. Isto não constitui um catálogo final de produtos,
entitlements ou preços e não prova que os módulos descritos no plano estejam
vendáveis.

## Decision

1. A arquitetura passa a distinguir três níveis que não são intercambiáveis:
   - **módulos de negócio do tenant**, que representam capacidades operacionais
     e podem futuramente ser agrupados em ofertas comerciais;
   - **capacidades de governação**, separadas entre Administração do Tenant e
     Administração SaaS do operador ROTAS;
   - **fundações técnicas transversais**, incluindo identidade, autorização,
     auditoria, ficheiros, sync/offline, idempotência e integrações.
2. Fundações técnicas não são módulos vendáveis nem itens de navegação. Cada
   módulo consumidor continua obrigado a provar os controlos transversais na
   sua jornada real.
3. `Clientes, Vendas e Cobrança` é o owner de contratos comerciais,
   `billing_items`, documentos de cobrança, contas a receber e recebimentos.
   `Custos e Margem` é owner de estimativas, custos reais, reconciliação e
   margem; pode consumir receita certificada, mas não emitir nem alterar
   documentos de cobrança.
4. Administração do Tenant e Administração SaaS são domínios distintos. O
   tenant não concede a si próprio planos, módulos pagos, limites ou acesso de
   suporte da plataforma.
5. A Oficina Intelligence Layer é uma especialização read-only de Business
   Intelligence. Não é um módulo comercial adicional e não escreve no núcleo
   transacional da Oficina.
6. Os valores atuais `tms` e `oficina` são bundles legados, não a taxonomia
   final de entitlement. E0 deve introduzir catálogo versionado de ofertas,
   capabilities, grants, limites, consumo e histórico, com migração
   `widen-migrate-narrow`; até lá não se anuncia licenciamento granular.
7. A secção 9 do plano mestre é inventário histórico/de escopo, não ordem de
   execução. A precedência executável é, por esta ordem:
   `AGENTS.md` -> C0-C4 -> Cliente/Terceiro -> E0-E5. A secção 10 explica as
   dependências e a secção 16 materializa E0-E5.
8. `legal_entity`, filial, centro de custo e sequência documental tornam-se
   entregáveis explícitos de E0, incluindo estratégia de backfill, reconciliação
   e rollback antes de qualquer fecho financeiro enterprise.
9. Páginas, rotas, models ou dashboards existentes não promovem um módulo. A
   matriz de fecho e o ledger devem mostrar lacunas reais, mesmo quando a
   superfície já existe.

## Alternatives Considered

### Reduzir o produto aos bundles `tms` e `oficina`

Rejeitado. Descreveria o código atual, mas abandonaria o objetivo aprovado de
ERP/TMS SaaS enterprise e transformaria dívida de implementação em redução
silenciosa de escopo.

### Tratar todos os quinze nomes como módulos já licenciáveis

Rejeitado. O catálogo, os entitlements, a navegação e vários fluxos
transacionais ainda não implementam essa promessa comercial.

### Transformar Suporte Técnico-Operacional num módulo comercial

Rejeitado. Identidade, auditoria, ficheiros e sync são controlos transversais e
não uma capacidade de negócio opcional que um tenant possa desativar.

### Renumerar imediatamente todas as waves históricas

Rejeitado. Produziria um diff documental grande, quebraria referências antigas
e não acrescentaria enforcement. A precedência explícita elimina a ambiguidade
sem reescrever o histórico.

## Consequences

- A taxonomia deixa de misturar produto, governação e infraestrutura.
- Billing permanece funcionalmente congelado; esta decisão apenas clarifica
  ownership documental.
- E0 passa a incluir a migração dos bundles legados e o retrofit explícito das
  dimensões legais/organizacionais.
- Navegação e catálogo comercial só serão alinhados depois de C0-C4 e da
  convergência Cliente/Terceiro, seguindo a sequência canónica.
- A decisão de release permanece `NO-GO`; nenhuma evidência de runtime foi
  criada por esta ADR.

## Supersession

Esta ADR complementa a ADR-009. Uma alteração da taxonomia ou da precedência
deve criar nova ADR e atualizar `AGENTS.md`, plano mestre, matriz de fecho e
ledger na mesma mudança.
