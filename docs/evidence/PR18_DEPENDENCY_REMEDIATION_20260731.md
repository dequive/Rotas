# PR-18 — Remediação Parcial de Dependências

Data: 2026-07-31  
Estado: `blocked_upstream_improved`  
Gate afectado: G4 — permanece vermelho

## Resultado

Foi reproduzido o PR-18 contra o registry actual e aplicada apenas a
remediação compatível com versões estáveis:

- `esbuild` raiz: `0.28.0 -> 0.28.1`;
- Driver `vite`: `5.4.21 -> 7.3.6`;
- Driver `@sentry/vite-plugin`: `2.x -> 5.4.0`;
- PostCSS directo do Manager fixado em `8.5.25`.

O grafo completo melhorou:

```text
antes: 1 moderate, 17 high, 0 critical
depois: 0 moderate, 13 high, 0 critical
```

A produção permanece em `3 high`, todos herdados de `next@16.2.12`:
`next`, o PostCSS interno `8.4.31` e Sharp `0.34.5`.

## Decisão sobre Next

O dist-tag estável actual continua `next@16.2.12` e fixa as duas dependências
vulneráveis. O canal canary já contém versões corrigidas, mas não foi promovido
para o ROTAS porque um prerelease não constitui remediação aceitável para o RC.

Foram testados overrides npm aninhados e globais. Eles não substituíram as
dependências internas exactas do Next; a auditoria permaneceu com 3 high. Os
overrides foram removidos e não fazem parte do estado final.

## Validação

```text
npm ls --all: exit 0, zero problemas
Produção: 0 moderate, 3 high, 0 critical
Completo: 0 moderate, 13 high, 0 critical
Driver: 26 testes, typecheck e build Vite 7.3.6 verdes
Manager: 89 testes, typecheck e build Next 72 páginas verdes
Dependency gate: NO-GO esperado
SBOM CycloneDX 1.5: 770 componentes
SBOM SHA-256: eb7e1e0195fe583386abccfa507568295dd544cda91985230ebd38fa0ace0801
```

O primeiro build Driver dentro da sandbox encontrou o bloqueio conhecido do
reparse point OneDrive. A repetição autorizada fora da sandbox passou.

## Continuação Redocly e Workbox

O `npm audit fix` sem `--force` actualizou
`@redocly/openapi-core 1.34.17 -> 1.34.18` e `js-yaml 4.2.0 -> 4.3.0`.
O advisory directo de `js-yaml` desapareceu, mas o total permanece 13 high
porque `openapi-typescript@7.13.0` continua ligado ao ramo Redocly v1, cujo
último release também está no intervalo vulnerável. Redocly v2 exige Node
20.19+/22 e uma migração de contrato que não pode ser tratada como patch.

Também foi ensaiada a combinação estável `vite-plugin-pwa@1.2.0` com Workbox
7.4.0 sugerida pelo audit. Ela manteve 13 high e reintroduziu 1 moderate,
trocando a cadeia Trickfilm por Surma/Terser/serialize-javascript. O downgrade
foi rejeitado e o estado final regressou a PWA 1.3.0/Workbox 7.4.1, que tem
menor severidade agregada.

Validação adicional:

```text
OpenAPI generated types check: green
Manager: 89 testes e typecheck green
Driver: 26 testes, typecheck e build PWA green
Árvore integral: exit 0, zero problemas
```

## Bloqueios restantes

- zero high/critical em produção;
- zero high/critical no grafo completo;
- repetição no Node 20 do RC;
- SBOM/provenance publicados e atestados no registry.

Artefactos machine-readable:

- `PR18_DEPENDENCY_GATE_20260731.json`;
- `PR18_CYCLONEDX_20260731.json`.

PR-18 continua `blocked_upstream`; PR-26 não pode iniciar.
