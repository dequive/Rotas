# ROTAS — Staging Production-like Runbook

## Estatuto

Este runbook prepara uma baseline provider-neutral. A presença dos Dockerfiles e
do Compose não prova que staging foi criado, promovido ou certificado.

## Pré-condições

- host Linux com Docker Engine e Compose v2;
- DNS público para Manager, Driver, API e Grafana;
- portas 80/TCP, 443/TCP e 443/UDP acessíveis;
- registry privado com retenção e referências por digest;
- secret manager capaz de materializar ficheiros temporários;
- bucket R2/S3 de staging;
- backup e owner operacional definidos.

O procedimento de backup/restore e os gates DR estão em
`docs/DR_BACKUP_RESTORE_RUNBOOK.md`.

## 1. Validar política estática

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\validate_staging_manifest.py
```

## 2. Construir no SHA candidato

Substituir `<sha>` pelo SHA integral do release candidate:

```powershell
docker buildx build --push --sbom=true --provenance=mode=max,version=v1 -f backend/Dockerfile --build-arg ROTAS_VERSION=<rc-version> --build-arg ROTAS_REVISION=<sha> -t registry/rotas/backend:<sha> .
docker buildx build --push --sbom=true --provenance=mode=max,version=v1 -f governance-engine/Dockerfile.production --build-arg ROTAS_VERSION=<rc-version> --build-arg ROTAS_REVISION=<sha> -t registry/rotas/governance:<sha> .
docker buildx build --push --sbom=true --provenance=mode=max,version=v1 -f apps/manager/Dockerfile --build-arg ROTAS_VERSION=<rc-version> --build-arg ROTAS_REVISION=<sha> -t registry/rotas/manager:<sha> .
docker buildx build --push --sbom=true --provenance=mode=max,version=v1 -f apps/driver/Dockerfile --build-arg ROTAS_VERSION=<rc-version> --build-arg ROTAS_REVISION=<sha> --build-arg VITE_ROTAS_API_BASE_URL=https://api.staging.example -t registry/rotas/driver:<sha> .
```

O BuildKit publica SBOM e provenance como attestations OCI. Executar também o
scanner aprovado e assinar cada digest com a identidade CI autorizada. Preservar
o relatório do scanner, a verificação da assinatura e das attestations no
release ledger. Depois do push, resolver o digest retornado pelo registry.
Tags, inclusive a tag baseada em SHA, não entram no manifesto de staging.

As attestations só contam depois do push para um registry que as preserve. O
image store Docker clássico não é fonte de prova suficiente. Para cada
`repository@sha256:<digest>`, guardar a saída JSON integral da verificação:

```powershell
cosign verify --certificate-identity <identidade-ci-exacta> --certificate-oidc-issuer <issuer-oidc-exacto> <repository@sha256:digest>
cosign verify-attestation --certificate-identity <identidade-ci-exacta> --certificate-oidc-issuer <issuer-oidc-exacto> <repository@sha256:digest>
```

Repetir a verificação de attestation para SBOM SPDX e provenance SLSA v1,
segundo a versão aprovada do Cosign, e validar o predicate devolvido. A política
de admissão do ambiente deve rejeitar imagem não assinada e provar que admitiu
exactamente o digest candidato. Não aceitar identidade, issuer, repositório,
revisão ou builder por substring/wildcard.

Copiar
`infra/staging/PR19_SUPPLY_CHAIN_BUNDLE.example.json` para o directório seguro
de evidência. Preencher as quatro imagens e os cinco ficheiros físicos por
imagem (`signature`, `sbom`, `provenance`, `scanner`, `admission`), sempre com
SHA-256 e SHA do release. O template é deliberadamente NO-GO.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.verify_supply_chain `
  --bundle C:\secure\PR19_SUPPLY_CHAIN_BUNDLE.json `
  --output C:\secure\PR19_SUPPLY_CHAIN_RESULT.json
```

Um `PASS` é apenas um fragmento de evidência do PR-19. Não certifica deploy,
TLS, secrets, migrations nem o G4 completo.

## 3. Preparar inputs e secrets

Copiar `infra/staging/staging.env.example` para um ficheiro protegido fora do
Git. Substituir as quatro imagens por referências
`registry/repository@sha256:<digest>` reais e configurar hosts/ACME.
`ROTAS_RELEASE_SHA` deve conter o SHA Git integral, em minúsculas, usado nos
quatro labels OCI. O backend expõe o mesmo valor em `/version`.

Materializar os ficheiros enumerados em
`infra/staging/secrets/README.md` num diretório temporário com acesso exclusivo
ao operador. As três URLs PostgreSQL do ROTAS devem usar:

- `DATABASE_URL`: `rotas_app`, sujeito a RLS;
- `ADMIN_DATABASE_URL`: `rotas_admin`, reservado a workers/control plane;
- `ALEMBIC_DATABASE_URL`: `rotas_admin`, reservado a migrations.

O webhook operacional do Alertmanager e a password administrativa inicial do
Grafana também são secrets externos. O acesso anónimo e o self-signup do
Grafana permanecem desactivados.

Validar inputs e secrets:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\validate_staging_manifest.py --env-file C:\secure\rotas-staging.env
```

## 4. Renderizar e promover

```powershell
docker compose --env-file C:\secure\rotas-staging.env -f infra\staging\docker-compose.yml config
docker compose --env-file C:\secure\rotas-staging.env -f infra\staging\docker-compose.yml pull
cd backend
.\.venv\Scripts\python.exe scripts\verify_staging_images.py --env-file C:\secure\rotas-staging.env
cd ..
docker compose --env-file C:\secure\rotas-staging.env -f infra\staging\docker-compose.yml up -d
```

As migrations são serviços one-shot e devem concluir antes de API ou
Governance aceitarem tráfego. A verificação intermédia falha se o digest
efectivamente puxado, utilizador não-root, versão ou label de revisão divergir
do manifesto. Não executar `alembic upgrade` no processo web.

## 5. Gates de promoção

1. `docker compose ps` mostra migrations concluídas e restantes serviços
   healthy.
2. `/health/deep` confirma DB, Redis e heartbeat do worker.
3. `/version` corresponde ao release candidate.
4. TLS e HSTS são verificados nos quatro hosts.
5. A API opera como `rotas_app`, nunca superuser/BYPASSRLS.
6. Smoke multi-tenant, outbox Governance, Driver offline e Manager BFF passam.
7. Métricas, logs e alertas aparecem no stack de observabilidade.
8. Backup/restore e rollback/forward-fix são exercitados.
9. Prometheus apresenta os targets e regras verdes; o dashboard
   `rotas-release-slos` está provisionado.
10. Cada alerta PR-20 é exercitado até `firing`, entregue e posteriormente
    `resolved` pelo canal operacional real.

## 5.1 Consolidar a evidência PR-19

Copiar
`infra/staging/PR19_STAGING_CERTIFICATION_CONTEXT.example.json` para o
directório seguro do release e preencher somente a partir dos outputs
observados no ambiente. O template é deliberadamente NO-GO.

O bundle exige nove ficheiros físicos:

- resultado `PASS` do gate de supply chain;
- quatro probes TLS/HSTS, um por host;
- relatório do secret manager e da ausência de secrets no ambiente runtime;
- outputs das migrations one-shot ROTAS e Governance;
- relatório runtime com `/version`, `/health/deep`, heartbeat e papel
  PostgreSQL efectivo.

Os outputs devem estar vinculados ao mesmo SHA, ter hashes SHA-256 e ser
recolhidos por runner externo. O início das aplicações deve ser posterior ao
fim das duas migrations.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.staging_certification `
  --context C:\secure\PR19_STAGING_CERTIFICATION_CONTEXT.json `
  --output C:\secure\PR19_STAGING_CERTIFICATION_RESULT.json
```

O resultado só pode alimentar os quatro controlos PR-19 do decisor G4 quando
`passed=true`, os quatro `controls` estão verdes e SRE/TL aprovam os hashes. Um
resultado local ou o template não é certificação de staging.

## 6. Rollback

Aplicações podem voltar ao digest anterior apenas quando a migration for
backward-compatible. Caso contrário, usar forward-fix aprovado. Nunca executar
downgrade destrutivo automaticamente.

Após a promoção, remover imediatamente os ficheiros temporários de secrets pelo
mecanismo seguro do host/secret manager e preservar somente hashes, digests,
timestamps e resultados dos gates.
