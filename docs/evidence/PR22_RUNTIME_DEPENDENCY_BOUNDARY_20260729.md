# PR-22 — Fronteira de Dependências do Runtime

Data: 2026-07-29  
Estado: `superseded_by_locked_runtime`  
Gate afectado: G4 — continua vermelho

> Actualização: a lacuna descrita abaixo foi fechada no âmbito local. O lock
> Python 3.11/Linux, a imagem e a execução multiprocess estão documentados em
> `PR22_LOCKED_CONTAINER_RUNTIME_20260729.md`. O diagnóstico histórico é
> preservado para rastreabilidade.

## Problema confirmado

O backend não possui lock de produção. O Docker executa `pip install .` sobre
intervalos abertos e a primeira build passou mais de vinte minutos a consultar
metadados e a fazer backtracking de versões Pydantic/FastAPI.

Também foi confirmado que o código importa diretamente:

- `pydantic`;
- `starlette`;
- `prometheus-client`.

Esses pacotes não estavam declarados como dependências diretas; chegavam apenas
por FastAPI ou pelo instrumentador Prometheus. Uma alteração transitiva podia,
portanto, mudar contratos usados diretamente pela aplicação.

## Correcção aplicada

O conjunto acoplado e já exercitado localmente foi declarado e fixado:

| Pacote | Versão |
| --- | --- |
| FastAPI | 0.136.3 |
| Pydantic | 2.13.4 |
| pydantic-settings | 2.14.1 |
| Starlette | 1.2.0 |
| prometheus-client | 0.25.0 |
| prometheus-fastapi-instrumentator | 8.0.0 |

Um teste de política lê `pyproject.toml` e falha se qualquer pacote desaparecer
ou deixar de ter a versão exacta aprovada.

O metadata editable foi regenerado sem dependências e `pip check` passou,
removendo a referência obsoleta a `python-jose` que ainda existia no
`egg-info` local. O runtime continua a usar PyJWT.

## Efeito observado na build

Depois da correcção:

- não houve novo backtracking Pydantic/FastAPI;
- a resolução chegou directamente às wheels;
- Pydantic core 2,1 MB concluiu;
- aiohttp 1,8 MB concluiu;
- a build ficou bloqueada durante o download de `botocore` 15,4 MB;
- nenhuma imagem foi produzida.

O cliente foi encerrado depois de mais de seis minutos sem progresso visível
nesse download. A dependência não foi removida porque suporta a integração
R2/S3.

## Validação

```text
Teste de política de dependências: green
Pytest focado:                    green
Ruff:                             green
Pyright:                          0 erros
pip check:                        no broken requirements
Dockerfile --check:               green
Imagem Linux:                     não produzida
```

## Fecho local posterior

Foi posteriormente gerado `requirements.lock`, validado em CI por política
fail-closed e instalado com `--require-hashes`. O resultado contém:

- 24 dependências directas;
- 69 pacotes bloqueados;
- 1902 hashes SHA-256;
- zero entradas editáveis/source/dev;
- `pip check` verde dentro da imagem.

A imagem Linux local foi produzida e executada. Permanecem pendentes o
`RepoDigest`/SBOM/attestation no registry, a reprodução no RC e a aprovação dos
budgets de carga. PR-22 permanece `in_progress`; G4 não muda.
