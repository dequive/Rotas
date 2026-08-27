# PR-18 — Verificação de Remediação Upstream

Data: 2026-07-31  
Estado: `blocked_upstream_confirmed`  
Gate afectado: G4 — permanece vermelho

## Objectivo

Antes de formar o release candidate ou considerar um waiver formal, foram
reavaliadas as versões publicadas e as correcções propostas pelo npm para os
findings PR-18. Nenhum upgrade forçado, override inválido ou release
canary/preview foi aplicado.

## Produção

O registry devolveu `next@16.2.12` como latest estável, exactamente a versão
instalada. O audit classifica como afectado o intervalo até
`16.3.0-preview.7` e propõe `next@9.3.3`, um downgrade major incompatível.

A cadeia observada permanece:

```text
next@16.2.12
  -> postcss@8.4.31
  -> sharp@0.34.5
```

Versões corrigidas isoladas existem:

```text
postcss latest: 8.5.25
sharp latest:   0.35.3
```

Contudo, o PostCSS é uma dependência interna exacta do Next e o Sharp é
solicitado por `^0.34.5`, que não aceita `0.35.3`. O override destas
dependências já produziu árvore `invalid` e continua rejeitado.

Resultado da auditoria de produção:

```text
high:     3
critical: 0
findings: next, postcss, sharp
```

## Grafo completo

O `npm audit fix --dry-run` manteve 13 high e 1 moderate. As propostas que
tocam high são downgrades:

- `openapi-typescript@7.13.0` para `6.7.6`;
- `vite-plugin-pwa@1.3.0` para `1.2.0`;
- `workbox-build@7.4.1` para `7.4.0`;
- `next@16.2.12` para `9.3.3`.

O downgrade PWA/Workbox já havia sido ensaiado e rejeitado porque não reduziu o
total high e reintroduziu risco moderate.

O downgrade OpenAPI TypeScript foi ensaiado fora do repositório:

```text
versão:                         6.7.6
opção --check:                  ausente
ficheiro actual v7.13.0:        23.250 linhas
ficheiro candidato v6.7.6:      16.862 linhas
hash actual:                    3b11d70a958ec97bc2d3d5c20167db1760fb6c703fb6e33d8c5ae4971bcb7eb4
hash candidato:                 a345b69c842815814543c91949226320168f0edd53e13516ea8b4fead36f991c
```

Além de remover o `--check` bloqueante do CI, o gerador antigo altera
materialmente o contrato TypeScript. Foi rejeitado.

## Decisão

Nenhuma modificação de dependência foi aplicada nesta etapa. As opções
tecnicamente íntegras são:

1. aguardar/adoptar uma versão estável do Next e das ferramentas que produza
   árvore válida com zero high; ou
2. submeter findings high a waivers reais, temporários e aprovados conforme o
   gate V2.

Nenhum waiver foi criado ou aprovado. PR-18 permanece `blocked_upstream`, G4
permanece vermelho e o release candidate ainda não pode ser promovido.

