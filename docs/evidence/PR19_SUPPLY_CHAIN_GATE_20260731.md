# PR-19 — Gate de Evidência da Supply Chain

Data da evidência: 2026-07-31  
Estado: `implemented_local_not_executed`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementado um gate fail-closed para verificar o bundle de supply chain
das quatro imagens aplicacionais do ROTAS. A ferramenta e o contrato estão
testados localmente, mas não existem ainda imagens do release candidate
publicadas, assinatura Cosign, attestations do registry, relatório do scanner
ou prova da política de admissão. O template devolve deliberadamente `NO-GO`.

O output da ferramenta é classificado como `release_evidence_fragment`. Mesmo
um `PASS` não certifica isoladamente PR-19 nem G4.

## Contrato verificado

Para Backend, Governance, Manager e Driver, o gate exige:

- referência única e imutável `repository@sha256:<digest>`;
- assinatura verificada para a identidade CI e issuer OIDC exactos;
- transparência verificada;
- SBOM attested com predicate SPDX;
- provenance SLSA v1 em modo `max`, vinculada ao repositório, SHA e builder;
- scanner com base fresca e zero vulnerabilidades high/critical;
- política de admissão efectivamente aplicada ao mesmo digest;
- cinco outputs físicos — assinatura, SBOM, provenance, scanner e admission —
  com SHA-256 válido e vínculo ao SHA integral do release.

O decisor rejeita conjunto parcial/extra de imagens ou evidências, tag mutável,
digest divergente entre secções, identidade/issuer divergentes, revisão
diferente, builder vazio, attestation falsa, finding high/critical, admissão
negada, ficheiro ausente ou hash físico divergente.

## Artefactos

- `backend/scripts/verify_supply_chain.py`
- `backend/tests/test_verify_supply_chain.py`
- `infra/staging/PR19_SUPPLY_CHAIN_BUNDLE.example.json`
- `docs/STAGING_DEPLOYMENT_RUNBOOK.md`
- `.github/workflows/ci.yml`

## Validação local

```text
Pytest focado:               5 passed
Ruff focado:                 green
Pyright focado:              0 errors, 0 warnings
Template PR-19:              NO-GO esperado
Cosign local:                indisponível
Registry/RC:                 não executado
```

O runbook passou a pedir provenance explícita `mode=max,version=v1` e regista
que o image store Docker clássico não constitui prova de attestations. A
verificação real deve ocorrer sobre os RepoDigests publicados e guardar os
outputs integrais do Cosign, scanner e admission controller.

## Bloqueadores mantidos

- release SHA, repositório/registry, identidade CI e issuer ainda não definidos;
- quatro imagens RC ainda não publicadas por digest;
- Cosign não está instalado nesta máquina e nenhuma assinatura foi verificada;
- SBOM/provenance do registry não foram obtidas nem validadas;
- scanner aprovado e política de admissão não foram executados;
- deploy, secrets externos, migrations, DNS/TLS e jornadas reais continuam
  pendentes;
- PR-18 ainda reporta vulnerabilidades high.

Conclusão: o controlo local reduz ambiguidade e impede promoção baseada apenas
em flags declarativas, mas PR-19 permanece `in_progress` e G4 permanece
vermelho.
