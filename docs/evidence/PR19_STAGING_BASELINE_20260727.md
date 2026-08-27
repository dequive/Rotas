# PR-19 — Baseline Endurecida de Staging

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations

## Resultado

Foi criada uma baseline provider-neutral e fail-closed para promover o ROTAS
para staging, mas nenhum ambiente remoto foi provisionado ou certificado.
Consequentemente, PR-19 deixou de estar `pending`, porém ainda não pode ser
declarado `done_local` nem G4 pode mudar para amarelo ou verde.

A baseline inclui:

- Compose de staging com API, worker, migrations, Governance, PostgreSQL,
  Redis, Manager, Driver e Caddy;
- redes de edge e dados separadas, sendo a rede de dados interna;
- apenas Caddy exposto, com TLS automático, HSTS e headers de segurança;
- imagens externas e `FROM` fixados por digest;
- quatro imagens aplicacionais exigidas como referências de registry por
  digest, sem fallback para tag;
- migrations one-shot antes da inicialização das aplicações;
- processos aplicacionais não-root, filesystem read-only, `cap_drop: ALL`,
  `no-new-privileges` e `tmpfs`;
- 18 secrets externos montados como ficheiros e consumidos apenas pelos
  processos autorizados;
- validação de produção fail-closed para JWT, CORS, Redis, R2, URLs HTTPS,
  database roles e credenciais Governance;
- runbook de build, push, digest, validação, promoção e rollback.

## Artefactos

- `infra/staging/docker-compose.yml`
- `infra/staging/Caddyfile`
- `infra/staging/Driver.Caddyfile`
- `infra/staging/staging.env.example`
- `infra/staging/secrets/README.md`
- `infra/staging/init-rotas-db.sh`
- `backend/Dockerfile`
- `governance-engine/Dockerfile.production`
- `apps/manager/Dockerfile`
- `apps/driver/Dockerfile`
- `backend/scripts/validate_staging_manifest.py`
- `backend/scripts/verify_staging_images.py`
- `docs/STAGING_DEPLOYMENT_RUNBOOK.md`

O CI passou a validar estaticamente a política de staging e a renderização do
Compose. O ficheiro de exemplo usa deliberadamente domínios e registry
inválidos; o validador rejeita-o quando usado como configuração de promoção.

O preflight de promoção exige agora:

- SHA Git integral de 40 caracteres, propagado para `/version`;
- quatro imagens distintas por digest;
- URLs PostgreSQL com os papéis `rotas_app`, `rotas_admin` e
  `governance_app`, incluindo coerência com os passwords externos;
- URL Redis autenticada e coerente com o secret;
- passwords com pelo menos 16 caracteres e chaves JWT/API/platform com pelo
  menos 32 caracteres, sem valores default;
- hosts distintos, R2 HTTPS e endereços operacionais reais;
- após o pull, `RepoDigest` exacto, utilizador não-root esperado, versão OCI
  não-development e label de revisão igual ao SHA promovido.

O runbook usa agora BuildKit com `--sbom=true` e
`--provenance=mode=max`; scanner, assinatura e verificação das attestations
continuam gates obrigatórios no registry escolhido.

## Gates locais reproduzidos

```text
Validador estático:                  green
  imagens externas literais:         4 por digest
  estágios Dockerfile:                8 por digest
  imagens aplicacionais exigidas:     4 por digest
Compose config --quiet:              green
Backend focused Pytest:              27 passed
Backend Ruff:                        green
Backend Pyright:                     0 erros, 0 warnings
Governance focused Pytest:           19 passed
Governance Ruff:                     green
git diff --check:                    green
```

As quatro imagens foram construídas localmente e executam como utilizadores
não-root:

| Imagem local | ID local | Utilizador |
| --- | --- | --- |
| `rotas-backend:pr19-local` | `sha256:188e8655813ecf0b19f89bcce8d93a59c2184021ac3c142df4fd02971e97047a` | `10001:10001` |
| `rotas-governance:pr19-local` | `sha256:481b16d055417d3d8e022b967439f703dde950e1151f5348cd7f1545221182eb` | `10001:10001` |
| `rotas-manager:pr19-local` | `sha256:a68ba02036b8d9de408b95cb2a82fb2f32d0fe94c7406e60365a0577f415ea21` | `node` |
| `rotas-driver:pr19-local` | `sha256:4ea821fa2e9004537da254b508d5f345f778e287ba9cc3082238a430fea14a7e` | `1000:1000` |

Backend passou `gunicorn --check-config` com configuração local mínima e
Governance importou a aplicação final. Manager `/login` e Driver `/` já haviam
respondido HTTP 200 em containers efémeros.

Estes IDs são IDs locais do Docker. Não são digests publicados num registry e
não constituem evidência de imagem promovível ou deploy remoto.

## Riscos e evidência ainda necessária

- seleccionar provider, conta/projecto, região, DNS e sizing;
- construir a partir do SHA do release candidate e publicar as quatro imagens
  num registry, com digests verificáveis;
- preservar/verificar SBOM e provenance OCI, produzir assinatura e aplicar
  política de admissão;
- fornecer os 18 secrets por secret manager/ficheiros externos autorizados;
- provisionar volumes, backups, firewall e acesso operacional;
- executar migrations numa base de staging e provar rollback/forward-fix;
- emitir certificados ACME para os quatro hostnames e testar renovação;
- validar R2, email, Redis, PostgreSQL e Governance reais;
- executar journeys multi-tenant, observabilidade, DR, carga e pentest;
- repetir os gates no CI remoto e no SHA do release candidate.

Os builds Node continuam a reportar 19 vulnerabilidades
(`17 high`, `2 moderate`) no grafo instalado. PR-18 permanece
`blocked_upstream`; esta baseline não altera nem aceita esse risco.

Além disso, as dependências Python ainda não estão integralmente congeladas por
hash. A imutabilidade na promoção será dada pelo digest da imagem publicada,
mas builds bit-a-bit reproduzíveis e supply-chain attestada continuam
pendentes.

Assim, o resultado correcto é `in_progress`: a baseline local existe e está
testada, mas staging real e G4 continuam vermelhos.
