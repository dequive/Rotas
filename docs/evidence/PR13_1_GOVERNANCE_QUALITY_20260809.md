# PR13.1 — Fecho da dívida Ruff do Governance

Data: 2026-08-09

Branch: `codex/pr13-1-governance-quality`

Base: `2aea4fb` (`codex/pr13-governance-contract`)

## Resultado

Estado: **done_local para os critérios próprios do PR13.1**; **não certificado
para release**.

O gate Ruff global do `governance-engine` passou de 153 ocorrências para zero.
O formatter canónico foi aplicado ao subprojeto completo, deixando os 41
ficheiros Python/TOML abrangidos pelo Ruff em estado estável e idempotente.

## Linha de base encerrada

| Regra | Antes | Depois | Tratamento |
| --- | ---: | ---: | --- |
| `B008` | 81 | 0 | factories FastAPI declaradas imutáveis no Ruff |
| `E501` | 64 | 0 | formatação estrutural de linhas longas |
| `F401` | 4 | 0 | imports não usados removidos |
| `I001` | 3 | 0 | imports normalizados |
| `E741` | 1 | 0 | variável ambígua renomeada |
| **Total** | **153** | **0** | |

`Depends`, `Security` e `require_scope` são factories declarativas avaliadas na
definição das rotas pelo FastAPI. Foram adicionadas a
`lint.flake8-bugbear.extend-immutable-calls`, que é o mecanismo próprio do Ruff
para este padrão; os endpoints, scopes e dependências não foram reescritos.

## Prova contra alteração comportamental

- A suite Governance completa passou após a formatação.
- O OpenAPI canónico antes e depois tem o mesmo SHA-256:
  `ada727b9ca363c29ba21b65506ea5f0dc848a281d24f4dba06d9de52314bedc1`.
- As únicas alterações não estritamente de layout são remoção de imports não
  usados, renomeação local de `l` para `location`, comentário explicativo e
  configuração Ruff.
- Nenhum ficheiro do backend ROTAS ou de billing foi alterado.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| `ruff check --no-cache .` | verde, 0 ocorrências |
| `ruff format --check .` | verde, 41 ficheiros formatados |
| Suite Governance em DB descartável | 47 passed |
| OpenAPI antes/depois | SHA-256 idêntico |
| `git diff --check` | verde |
| Alterações em billing | 0 ficheiros |

Os testes usaram `governance_pr13_gate2` no contentor descartável
`rotas-pr13-governance-db`. Nenhuma migração nem operação destrutiva foi
executada sobre a base ROTAS original.

## Limites preservados

- A divergência histórica ORM/SQL do Governance não foi alterada; pertence ao
  PR13.2.
- Retry/backoff, `SKIP LOCKED`, DLQ e reconciliação continuam no PR14.
- Não houve migração de produção, deploy ou promoção de imagem.

## Decisão de gate

- Critério PR13.1 — Ruff global e formato canónico: **verde local**.
- Próximo passo obrigatório: **PR13.2 — reconciliação ORM/SQL**.
- Release global: **NO-GO** até fechar PR13.2, PR14, revisão independente e CI
  no SHA candidato.
