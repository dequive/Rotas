# C3 — Remediação local de dependências e build Node 20 — 2026-08-27

- Branch: `codex/issue42-convergencia-manager-driver-backend`.
- Commit técnico: `0271ae0`.
- Runtime canónico: Node `20.20.2`, npm `10.8.2`, Linux glibc.
- Classe de evidência: engenharia local; não é release candidate.
- Decisão global: `NO-GO`.

## Alterações comprovadas

- Next e SWC Linux foram alinhados em `16.3.3`; o lockfile foi regenerado do
  zero no runtime canónico, sem `audit fix --force`.
- Vitest foi fixado em `4.1.11` nos dois workspaces e a configuração Manager
  deixou de declarar a propriedade `oxc` fora do contrato tipado atual.
- O Driver passou a citar o glob `e2e/**`, impedindo o shell Linux de entregar
  specs Playwright ao Vitest, e deixou de usar `--configLoader native`, que não
  carrega `vite.config.ts` no Node 20.
- O teste de reavaliação de saída aguarda o fim observável da primeira operação;
  cinco repetições consecutivas passaram sob filesystem lento.
- O gate PR18 mantém fail-closed todos os problemas inesperados. A única
  classificação aceite exige simultaneamente o par exato
  `@img/sharp-wasm32@0.35.4` + `@emnapi/runtime@1.11.3`, URLs oficiais do
  registry, flags `extraneous`, caminhos e relação pai-filho. Mudança de versão,
  origem, forma ou problema adicional bloqueia o gate.

O par acima é reproduzível num lockfile criado do zero e decorre dos wrappers
opcionais de plataforma do Sharp. As referências upstream são o
[`package.json` do Sharp](https://github.com/lovell/sharp/blob/main/package.json)
e a discussão de instalação WASM 0.35.x
[#4576](https://github.com/lovell/sharp/issues/4576).

## Resultados locais

- `npm audit --omit=dev`: `0` vulnerabilidades;
- `npm audit`: `0` vulnerabilidades;
- gate `PR18-DEPENDENCY-SECURITY-V2`: `passed=true`, zero blockers, ambos os
  audit commands válidos, árvore válida e Node 20 confirmado;
- SBOM CycloneDX 1.5: `759` componentes, SHA-256
  `3ab1e6c5447fd602fb10167a7f26cb0ef280157bdb06ec0ec5dec2cb0b746d3a`;
- contratos backend C3/PR18: `18/18`; Ruff focado verde;
- Manager: `128/128`, typecheck verde e build Next de `74` páginas;
- Driver: `67/67`, typecheck verde e build PWA verde: `1806` módulos cliente,
  `94` módulos do service worker e `6` entradas de precache;
- runtime standalone Manager removeu Sharp e os pacotes PostCSS não usados,
  conforme `PR18-MANAGER-RUNTIME-SURFACE-V1`.

## Limites e próximo gate

Esta evidência fecha localmente a remediação #37/PR18 e a dívida supply-chain
conhecida, mas não fecha C3 nem G0. O perfil executado foi `local`; ainda faltam
CI GitHub com passos reais, revisão independente SEC/TL, SHA integrado, execução
`release_candidate`, artefactos/attestations e merge. Billing e a base de dados
online permaneceram intocados.
