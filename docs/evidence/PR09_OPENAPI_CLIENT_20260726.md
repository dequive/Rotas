# PR-09 — Contrato OpenAPI e Cliente Manager Gerado

Data: 2026-07-26  
Estado: `done_local`

## Resultado

O FastAPI é agora a fonte canónica de um contrato OpenAPI 3.1 versionado e
determinístico:

```text
backend/openapi/rotas-v1.json
SHA-256: 5dd8aee0621762307eb46840abb924a2012bd1d5a936220a832105a8ea77ed2b
300 paths
367 operações
217 schemas
```

`backend/scripts/export_openapi.py`:

- gera JSON com chaves ordenadas;
- exige OpenAPI 3.x e pelo menos um path;
- exige `operationId` presente e único em todas as operações;
- falha em `--check` quando o contrato versionado diverge da aplicação.

O Manager gera:

```text
apps/manager/app/generated/rotas-api.ts
```

com `openapi-typescript 7.13.0`. O comando `--check` falha quando os tipos
gerados divergem do JSON versionado.

## Cliente runtime

`generated-api-client.ts` instancia `openapi-fetch` com os `paths` gerados. O
transporte customizado:

- preserva tipagem de path, parâmetros, body, respostas e erros;
- remove qualquer cabeçalho `Authorization` proveniente do browser;
- encaminha todas as operações pelo Manager BFF;
- mantém access/refresh tokens exclusivamente no servidor.

O teste runtime confirmou que uma operação OpenAPI tipada usa o BFF e não
constrói autenticação no browser.

## Evidência

```text
Contrato backend: 2 passed
Ruff: verde
Pyright integral: 0 erros
BFF inventory: 95 módulos client-side, 0 violações
Manager Vitest: 15 ficheiros, 76 testes passed
Manager TypeScript: verde
Manager Next build: verde, 72 páginas
```

O CI executa:

1. comparação FastAPI → JSON versionado;
2. comparação JSON → tipos TypeScript;
3. testes backend e Manager;
4. typecheck e builds.

## Limites

- A migração dos helpers manuais para o cliente gerado será incremental no
  PR-10; misturar todos os consumidores numa única alteração aumentaria o
  risco operacional.
- A evidência ainda precisa de reprodução no SHA do release candidate pela CI
  remota.
- A auditoria npm continua vermelha. `openapi-typescript` é uma dependência
  exclusivamente de desenvolvimento, mas a sua cadeia Redocly possui advisory
  high sem correção compatível na versão estável atual. Isso permanece
  contabilizado em PR-18/G4 e não é aceite como release green.
