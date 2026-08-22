# PR-18 — Gate de Dependências e SBOM Reproduzível

Data: 2026-07-30  
Estado: `blocked_upstream_improved_local`  
Gate afectado: G4 — continua vermelho

## Resultado

O PR-18 continua bloqueado, mas o grafo completo e a fronteira de evidência
foram corrigidos.

Antes da alteração:

```text
npm ls --all: exit 1
problema: esbuild@0.21.5 inválido para Vite 8 (^0.27 || ^0.28)
npm sbom: ESBOMPROBLEMS
```

Vitest 4 instala Vite 8, enquanto a aplicação Driver usa Vite 5. O único
`esbuild@0.21.5` hoisted satisfazia Vite 5, mas tornava inválido o peer opcional
observado por Vite 8.

Foi adicionada a dependência raiz exacta `esbuild@0.28.0`. O lock passou a
resolver:

```text
root/Vitest/Vite 8 -> esbuild 0.28.0
Driver/Vite 5      -> esbuild 0.21.5 isolado
```

Depois da alteração:

```text
npm ls --all: exit 0
problemas estruturais: 0
CycloneDX: 1.5
componentes: 787
SBOM SHA-256: 9320b0efb04ca87291d9c5c0b76c6710ae0d2ecd1846fd0cff2bf906518df570
```

O gerador foi tornado explicitamente UTF-8 e grava o SBOM em bytes canónicos.
Isso corrigiu uma divergência LF/CRLF detectada no Windows; o hash do ficheiro
físico agora corresponde ao relatório.

## Auditoria actual

| Âmbito | Moderate | High | Critical |
| --- | ---: | ---: | ---: |
| Produção | 0 | 3 | 0 |
| Completo | 1 | 17 | 0 |

Os pacotes de produção continuam:

- `next`;
- `postcss`;
- `sharp`.

O relatório machine-readable mantém:

```text
passed = false
blockers =
  production_zero_high_critical
  complete_zero_high_critical
  node_20
sbom.attested = false
```

## Regressão

```text
Manager: 19 ficheiros, 89 testes
Driver:   5 ficheiros, 26 testes
Typecheck Manager/Driver: green
Manager build: 72 rotas
Driver build: 1.808 módulos, 93 módulos SW, 6 entradas precache
Dependency gate unit tests: 2 passed
```

O primeiro build Driver dentro da sandbox falhou por acesso OneDrive/esbuild;
a repetição externa passou e é a execução considerada.

## Artefactos

- `PR18_DEPENDENCY_GATE_20260730.json`;
- `PR18_CYCLONEDX_20260730.json`;
- `scripts.dependency_security_gate`.

## Limite

O SBOM é local e `attested=false`. O runtime usado foi Node 24.16.0/npm 11.13.0,
não Node 20 do RC. PR-18 só pode ficar verde quando:

1. produção e grafo completo tiverem zero high/critical;
2. árvore integral continuar válida;
3. o mesmo gate passar no SHA do RC em Node 20;
4. SBOM/provenance forem publicados e verificados no registry.

Até lá, PR-18 permanece `blocked_upstream`, G4 permanece vermelho e PR-26
continua bloqueado.

