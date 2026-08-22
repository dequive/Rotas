# PR-18 — Validação Local no Runtime Node 20

Data: 2026-07-31  
Estado: `validated_local`, não certificado no RC  
Gate afectado: G4 — permanece vermelho

## Runtime

Foi usado o arquivo oficial `node-v20.20.2-win-x64.zip`, descarregado da
distribuição Node.js e validado antes da extracção:

```text
Node: v20.20.2
npm: 10.8.2
SHA-256 publicado:
dc3700fdd57a63eedb8fd7e3c7baaa32e6a740a1b904167ff4204bc68ed8bf77
SHA-256 observado:
dc3700fdd57a63eedb8fd7e3c7baaa32e6a740a1b904167ff4204bc68ed8bf77
```

O runtime foi extraído apenas em `C:\tmp`; não substituiu o Node global nem
alterou a imagem de release.

## Gate PR-18

O agregador foi executado com o runtime temporário no início do `PATH`:

```text
node_20: true
dependency_tree_valid: true
cyclonedx_sbom_generated: true
production_zero_high_critical: false
complete_zero_high_critical: false
decision: NO-GO
```

O blocker local `node_20` deixou de existir. Permanecem os blockers de
vulnerabilidades high:

```text
Produção, npm 10: 3 high, 1 moderate, 0 critical
Completo, npm 10: 13 high, 1 moderate, 0 critical
```

O moderate adicional reportado pelo npm 10 é `@sentry/nextjs`, embora a versão
instalada 10.67.0 esteja fora do intervalo 6.3.6–10.19.0 apresentado pelo
próprio relatório. A divergência entre npm 10 e npm 11 foi preservada como
evidência; não foi silenciosamente descartada. O PR-18 bloqueia high/critical,
mas a divergência precisa ser reconciliada no RC.

## Validação das aplicações

```text
Manager:
  89 testes
  typecheck green
  Next build green, 72 páginas

Driver:
  26 testes
  typecheck green
  Vite 7.3.6 build green
  PWA injectManifest, 93 módulos SW, 6 entradas precache
```

O primeiro build Manager encontrou um lock `EPERM` num output `.next/static`
gerado pela execução anterior. O caminho absoluto foi validado, apenas `.next`
foi removido e a reconstrução limpa terminou verde.

## SBOM local Node 20

```text
CycloneDX: 1.5
Componentes: 859
SHA-256: 58626c0dbdde5b18d1e1b875f58aa0b8454b6218c5aaafd446dc7aacd90583c4
Attested: false
```

Artefactos:

- `PR18_DEPENDENCY_GATE_NODE20_LOCAL_20260731.json`;
- `PR18_CYCLONEDX_NODE20_LOCAL_20260731.json`.

## Limite

Esta execução prova compatibilidade local com Node 20.20.2. Não prova:

- o SHA/RepoDigest do release candidate;
- execução dentro das quatro imagens imutáveis;
- publicação e verificação do SBOM/provenance;
- attestation no registry;
- zero high/critical.

Logo, PR-18 continua `blocked_upstream` e PR-26 permanece bloqueado.
