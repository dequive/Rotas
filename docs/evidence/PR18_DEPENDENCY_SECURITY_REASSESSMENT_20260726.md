# PR-18 — Reavaliação de Segurança das Dependências

Data da evidência: 2026-07-26  
Estado: `blocked_upstream`  
Gate afectado: G4 — Production Operations

## Resultado

O PR-18 não pode ser declarado concluído. O grafo instalado contém
`next@16.2.11 -> sharp@0.34.5`, enquanto o advisory
`GHSA-f88m-g3jw-g9cj` afecta versões de Sharp anteriores a `0.35.0`.

O `npm audit` actual também identifica vulnerabilidades high que não se limitam
ao Sharp:

| Escopo | Info | Low | Moderate | High | Critical |
| --- | ---: | ---: | ---: | ---: | ---: |
| Produção (`--omit=dev`) | 0 | 0 | 0 | 4 | 0 |
| Grafo completo | 0 | 0 | 1 | 17 | 0 |

Pacotes high no escopo de produção: `brace-expansion`, `next`, `postcss` e
`sharp`.

Pacotes high no grafo completo:
`@redocly/openapi-core`, `@sentry/bundler-plugin-core`,
`@sentry/vite-plugin`, `@trickfilm400/rollup-plugin-off-main-thread`,
`brace-expansion`, `ejs`, `filelist`, `glob`, `jake`, `js-yaml`, `minimatch`,
`next`, `postcss`, `sharp`, `vite`, `vite-plugin-pwa` e `workbox-build`.

## Comandos reproduzidos

```powershell
npm ls next sharp --all
npm audit --omit=dev --json
npm audit --json
```

Árvore relevante:

```text
@rotas/manager@0.1.0
`-- next@16.2.11
    `-- sharp@0.34.5
```

A execução local usou Node `v24.16.0` e npm `11.13.0`, mas o repositório exige
Node `20.x`. Os mesmos gates devem ser repetidos no Node 20 do CI antes de
qualquer promoção.

## Mitigação avaliada e rejeitada

Foram avaliados:

1. override global de `sharp` para `0.35.3`;
2. override de `sharp` sob `next`;
3. dependência directa `sharp@0.35.3` no Manager.

Nenhuma opção removeu `node_modules/next/node_modules/sharp@0.34.5`. A
dependência directa apenas criou uma segunda versão, sem alterar a versão
resolvida internamente pelo Next. As três alterações foram retiradas para não
registar uma mitigação aparente que não fecha o advisory.

Não foi aplicado `npm audit fix --force`, remoção manual da dependência interna
ou alteração manual do lockfile: essas opções são breaking, não suportadas ou
não reproduzíveis.

## Evidência externa verificada

- npm apresenta `next@16.2.11` como versão estável mais recente na data desta
  reavaliação.
- npm apresenta `sharp@0.35.3` como versão disponível corrigida.
- O advisory GitHub `GHSA-f88m-g3jw-g9cj` classifica como high as versões
  `sharp < 0.35.0`.
- A issue upstream `vercel/next.js#96064` documenta o mesmo bloqueio no
  `next@16.2.11` e permanece aberta.

Referências:

- https://www.npmjs.com/package/next?activeTab=versions
- https://www.npmjs.com/package/sharp
- https://github.com/advisories/GHSA-f88m-g3jw-g9cj
- https://github.com/vercel/next.js/issues/96064

## Critérios de desbloqueio

PR-18 só pode avançar para `done_local` quando, no mesmo grafo e lockfile:

1. uma versão suportada do Next deixar de instalar Sharp vulnerável;
2. `npm ls next sharp --all` não mostrar nenhuma versão afectada;
3. `npm audit --omit=dev` reportar zero high/critical;
4. a auditoria completa reportar zero high/critical, ou cada excepção possuir
   waiver formal com owner, prazo, compensação e aprovação SEC;
5. testes, typecheck e builds passarem no Node 20;
6. o resultado for reproduzido no SHA do release candidate pela CI remota.

Até lá, G4 permanece vermelho e o estado global continua `NO-GO`.
