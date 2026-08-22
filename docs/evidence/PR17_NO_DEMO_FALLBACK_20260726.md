# PR-17 — Zero dados demo nas jornadas de release

Data: 2026-07-26  
Estado: `done_local`  
Escopo validado: Manager runtime, CI, Playwright, configuração e bundle Next

## Alterações

- removidos os datasets fictícios de cobrança, documentos de cobrança, torre
  de controlo, históricos de frota, controlo de combustível e despacho;
- removido o runtime guard que permitia reactivar os dados fictícios por flag;
- removidas `ROTAS_ALLOW_DEMO_FALLBACK` e
  `ROTAS_DISABLE_DEMO_FALLBACK` do CI, Playwright e `.env.example`;
- falha de API passa a propagar erro ou estado explicitamente indisponível;
- uma API válida sem entidades devolve estado vazio, sem fabricar viatura,
  motorista, viagem, cliente, tanque, margem ou documento;
- tabela de despacho não configurada usa estrutura vazia, desactivada e sem
  faixas/valores inventados;
- `DataSourceBadge` distingue `api`, `cache` e `unavailable`; deixou de existir
  a fonte `fallback`;
- CI executa um gate bloqueante antes dos testes/builds do frontend.

## Gate anti-regressão

`verify-no-demo-fallback.mjs` inspecciona a superfície de produção e falha para:

- flags que autorizem ou desactivem demo fallback;
- runtime guards permissivos;
- `source: "fallback"` ou `source="fallback"`;
- nomes dos antigos datasets fictícios;
- IDs fabricados `vehicle-demo-*` e `driver-demo-*`.

Testes do gate provam rejeição dos padrões proibidos, aceitação de estado vazio
real e conformidade do source tree actual.

## Evidência local

```text
Gate source: passed
Gate tests: 3/3 passed
Manager typecheck: 0 erros
Manager Vitest: 17 ficheiros, 86 testes, 86 passed
Manager Next 16.2.11 build: 72 páginas, exit code 0
Bundle scan: zero ocorrências dos antigos IDs, clientes, tanques e flags demo
git diff --check: passed
```

O primeiro build excedeu o timeout depois de compilar e iniciar o typecheck; não
foi usado como prova. As execuções completas seguintes terminaram com código
zero, incluindo o build final no estado exacto da source validada.

## Limites de certificação

- os testes locais e o build não substituem CI no SHA do release candidate;
- o gate comprova ausência dos padrões e datasets conhecidos, não a qualidade
  ou disponibilidade das APIs reais;
- as jornadas E2E do Manager contra backend/staging real continuam necessárias;
- dados de seed explicitamente executados em ambientes de teste/piloto não são
  fallback de runtime, mas também não certificam produção.

Esta evidência fecha os critérios de engenharia local do PR-17. O release
global permanece `NO-GO`.
