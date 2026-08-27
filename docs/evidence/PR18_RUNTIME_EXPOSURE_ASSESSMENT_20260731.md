# PR-18 — Avaliação de Exposição Runtime

Data: 2026-07-31  
Estado: `mitigated_local`, certificação RC pendente  
Gate afectado: G4 — permanece vermelho

## Âmbito

Esta avaliação determina se os três findings de produção observados no
`npm audit` são alcançáveis no Manager executado. Redução de superfície não
remove findings do SBOM nem equivale a waiver aprovado.

## PostCSS

Os advisories high dependem de CSS controlado pelo atacante alcançar o
processamento PostCSS com `sourceMappingURL`. No ROTAS:

- não existe upload de CSS;
- não existe pipeline PostCSS exposto por API;
- o PostCSS do Next é utilizado durante o build;
- a inspecção física do `.next/standalone` encontrou zero pacotes PostCSS.

Classificação: exposição runtime não demonstrada. Pode ser considerado para
waiver temporário apenas se a imagem Linux do RC continuar sem PostCSS e o
RepoDigest for o mesmo verificado em PR-19.

## Sharp/libvips

O advisory Sharp afecta processamento de input não confiável antes de 0.35.0.
O ROTAS aceita evidências JPEG/PNG/WebP controladas por tenants, portanto a
simples presença de Sharp no runtime era incompatível com uma alegação de
baixa exposição.

Foram aplicados controlos fail-closed:

1. `images.unoptimized=true`;
2. zero imports `next/image`;
3. zero `remotePatterns`, `dangerouslyAllowLocalIP` ou SVG perigoso;
4. o build remove apenas `sharp` e pacotes `@img/sharp-*` do standalone;
5. o build falha se a optimização for reactivada ou surgir um import;
6. o workflow RC verifica ausência física e publica
   `runtime-surface.json`.

Prova local Node 20:

```text
Manager tests:             89 passed
PR-18/G4 focused tests:    14 passed
typecheck:                 green
build:                     72 páginas
Sharp no standalone:       0
PostCSS no standalone:     0
/login:                    HTTP 200
/_next/image:              HTTP 404
runtime policy:            PR18-MANAGER-RUNTIME-SURFACE-V1
```

Classificação: mitigado no standalone local, mas ainda não elegível para
aprovação final. A primeira construção Docker Linux terminou por queda do
daemon durante `npm ci` (`RPC EOF`). Depois da recuperação, `npm ci` instalou
859 pacotes, mas o Next tentou descarregar SWC na fase de build e falhou por
DNS. Isso revelou uma dependência tardia de rede incompatível com build
reproduzível.

O contrato Docker foi endurecido:

- `@next/swc-linux-x64-gnu@16.2.12` passou a optional dependency directa e
  lockada;
- `npm ci --include=optional` instala o grafo;
- o Dockerfile exige fisicamente o binário SWC antes de compilar;
- a compilação usa `RUN --network=none`, impedindo downloads tardios.

`npm ci --dry-run` confirmou o SWC Linux e os quatro testes do contrato
passaram. Em 2026-08-01, a reconstrução Linux instalou 860 pacotes, encontrou
o binário obrigatório e compilou 72 páginas com a rede desligada. A imagem
local resultante tem identidade
`sha256:3ad89e88e1293629f77d3eaa7d3163c9b583f57cd18b5f93f5965a0606c4933f`.

A inspeção física não encontrou diretórios runtime `sharp`, `postcss` ou
`@img/sharp-*`. O manifesto em `/app/pr18-runtime-surface.json` confirma a
política `PR18-MANAGER-RUNTIME-SURFACE-V1`, optimizador desactivado, zero
imports `next/image` e os três pacotes removidos. Num contentor real,
`/login` respondeu HTTP 200 e `/_next/image` HTTP 404.

Esta é evidência local da imagem, não um RepoDigest de RC publicado: os labels
continuam `version=dev` e `revision=unknown`, sem registry, SHA de release,
assinatura ou attestation verificadas. Portanto PR-18/G4 permanecem vermelhos.

## Finding agregado Next

O npm propaga os findings PostCSS e Sharp para `next`. O finding agregado só
pode ser considerado coberto quando ambos os componentes forem comprovadamente
ausentes do artefacto runtime do RC. A configuração fonte isolada não basta.

## Ferramentas de desenvolvimento

OpenAPI TypeScript/Redocly e PWA/Workbox são executados apenas sobre fontes
versionadas durante CI/build. O workflow CI passou a declarar explicitamente
`permissions: contents: read`, reduzindo a autoridade do código executado em
pull requests. Esses findings continuam presentes no grafo completo e exigem
remediação ou waivers próprios; não herdam automaticamente a avaliação do
runtime Manager.

## Decisão

| Finding | Estado técnico | Waiver agora? |
| --- | --- | --- |
| PostCSS | ausente do standalone local | não; falta imagem RC Linux |
| Sharp | removido do standalone e endpoint inactivo | não; falta imagem RC Linux |
| Next agregado | depende dos dois controlos acima | não |
| Dev tooling | build-only, CI read-only | não; avaliação individual pendente |

Nenhum risco foi aceite. PR-18 continua `blocked_upstream`, G4 permanece
vermelho e PR-26 continua bloqueado.
