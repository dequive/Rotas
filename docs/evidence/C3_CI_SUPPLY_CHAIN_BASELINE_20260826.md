# C3 — Baseline local de CI e supply chain — 2026-08-26

- Classe: evidência de engenharia local; não é CI remota nem certificação de release.
- Branch: `codex/issue42-convergencia-manager-driver-backend`.
- Commit dos controlos C3: `9cb2abe`.
- Produto Driver previamente certificado no Android: `a978229`.
- Decisão: `NO-GO`.

## Controlos corrigidos

- As 12 referências remotas dos workflows atuais usam SHAs lowercase de 40
  caracteres e apenas o proprietário GitHub-owned `actions` é permitido.
- `ci.yml` executa o validador e os seus testes antes dos restantes gates.
- Os dois jobs Node usam `20.20.2`, alinhados com `.node-version`, `.nvmrc` e
  `package.json`.
- A CI passa a executar Vitest Driver, build Driver e as jornadas Playwright
  Driver; o typecheck raiz continua a cobrir todos os workspaces.
- O teste PR18 deixou de exigir a referência mutável `upload-artifact@v4` e
  exige SHA completo.

## Evidência local

- RED: 12 referências mutáveis rejeitadas pelo teste integral dos workflows.
- GREEN: 6/6 testes do validador; 12/12 referências aprovadas.
- Contratos CI/PR18/governance: 8/8 numa base descartável `template0 -> rec16`.
- Ruff focado: verde; parse YAML dos três workflows: verde; `git diff --check`:
  verde.
- Os gates funcionais chamados pela nova CI já tinham passado no produto
  congelado: Driver 67/67, build e Playwright 7/7.

## Auditoria de dependências no runtime canónico

O grafo versionado foi reconstruído a partir de `git archive 49f0fac` com
`npm ci --ignore-scripts` no contentor efémero `node:20-bookworm-slim`, que
reportou Node `20.20.2` e npm `10.8.2`. O blob de `package-lock.json` é o mesmo
em `49f0fac` e `9cb2abe`: `68f7d33aed0bb36a1039d1f95e0d33c868ae47ee`.

A consulta direta ao advisory service produziu:

- produção: 6 high, 0 critical — `brace-expansion`, `fast-uri`, `nanoid`,
  `next`, `postcss` e `sharp`;
- árvore completa: 9 high, 0 critical — acrescenta
  `@redocly/openapi-core`, `js-yaml` e `undici`;
- `npm ls --all`: um problema, `@emnapi/runtime@1.11.1` extraneous;
- SBOM CycloneDX 1.5: 860 componentes, sem attestation de registry.

O agregador PR18 devolveu contagens zero numa execução apesar de o `npm ci` e
as duas consultas diretas devolverem high. Essa inconsistência é tratada de
forma fail-closed: o resumo zero não é aceite como prova de segurança. Os JSON
brutos permanecem em `.release-evidence/c3-node20-clean/`, fora do Git.

## Bloqueios

1. Remediar as dependências high e o pacote extraneous num slice dedicado C3,
   com lockfile reproduzível e regressão completa; não usar `npm audit fix
   --force`.
2. Endurecer o agregador PR18 para rejeitar respostas incompletas/contraditórias
   e preservar a proveniência dos resultados brutos.
3. Executar os jobs remotos com passos reais no SHA integrado. A conta GitHub
   continua indisponível, portanto não existe prova remota.
4. Revisão independente, merge, RC, staging e C4 continuam pendentes.

Nenhuma alteração foi feita ao billing ou à base de dados online.
