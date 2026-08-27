# PR-22 — Runtime Linux Bloqueado e Curva de Concorrência

Data: 2026-07-29  
Estado: `validated_local_red_performance`  
Gate afectado: G4 — continua vermelho

## Resultado

Foi produzida e executada localmente uma imagem Linux reproduzível do backend:

```text
Tag local:       rotas-backend:pr22-multiprocess
Image ID:        sha256:0fc81e0cfc25b1fdc64a2ed31edc75751d691df42cc7b21ac7474273a1455296
Tamanho:         124362493 bytes
Criada em:       2026-07-29T21:52:26.593271669Z
Runtime:         Gunicorn 26, quatro workers Uvicorn
```

O identificador acima é da imagem local, não um `RepoDigest` de registry e não
autoriza promoção.

## Dependências reproduzíveis

`requirements.lock` foi compilado para Python 3.11/Linux e é instalado com
`pip --require-hashes`:

| Controlo | Resultado |
| --- | ---: |
| Dependências directas validadas | 24 |
| Pacotes bloqueados | 69 |
| Hashes SHA-256 | 1902 |
| Entradas editáveis/source/dev | 0 |
| `pip check` dentro da imagem | sem dependências quebradas |

O Docker instala primeiro o lock e só depois copia a aplicação, preservando a
camada de dependências. A aplicação é instalada sem resolução adicional com
`--no-deps --no-build-isolation`.

## Boot production-like

O container foi executado com filesystem read-only, `/tmp` em `tmpfs`,
`cap-drop ALL`, `no-new-privileges`, utilizador não-root, diagnósticos de
performance desligados, PostgreSQL acessível pelo papel operacional restrito
`rotas_app`, conexão administrativa separada e Redis.

Quatro workers iniciaram e `/health` ficou verde. Gunicorn usa
`--no-control-socket`, necessário porque a versão 26 tenta criar por default um
socket no home read-only do utilizador.

## Métricas multiprocess e restart

O scrape agregado mostrou:

```text
application:    base_size=8, max_connections=20, checked_out=0
administrative: base_size=8, max_connections=20, checked_out=0
```

Isto corresponde a quatro workers vezes `pool_size=2` e
`pool_size + max_overflow=5` por engine.

No drill de restart, o worker PID 26 terminou e o PID 85 foi criado. O ficheiro
`gauge_livesum_26.db` desapareceu e os ficheiros dos PIDs 27, 28, 29 e 85
permaneceram. A capacidade final continuou 20/20, provando a chamada
`mark_process_dead` no runtime Linux. Durante o encerramento gracioso apareceu
uma mensagem isolada `Bad file descriptor`; o master repôs o worker e o serviço
continuou saudável.

## Curva de concorrência

Todos os pedidos abaixo devolveram HTTP 200, sem erros inesperados:

| Concorrência | Pedidos | p50 ms | p95 ms | p99 ms | Resultado |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 100 | 60,561 | 135,792 | 159,436 | passou |
| 4 | 300 | 152,869 | 395,153 | 573,445 | falhou |
| 8 | 300 | 450,958 | 942,881 | 1734,625 | falhou |
| 12 | 600 | 325,200 | 686,902 | 1060,842 | falhou |
| 12, com scrape | 600 | 307,632 | 504,025 | 916,523 | falhou |

No ensaio amostrado de concorrência 12 houve 27 scrapes, zero erros de scrape e
máximos de:

- application: 4/20 conexões, 20%;
- administrative: 3/20 conexões, 15%.

Os dados mostram um joelho de concorrência forte, mas não saturação do pool. A
próxima investigação deve medir CPU/event loop e round-trips SQL num runner
externo com `pg_stat_statements`, em vez de aumentar pools sem evidência.

## Veredicto e pendências

Esta execução fecha localmente as lacunas de lock, boot Linux, quatro workers,
agregação de capacidade e limpeza de séries mortas. Não certifica RC, staging
ou produção.

PR-22 continua `in_progress` e G4 continua vermelho porque ainda faltam:

1. imagem publicada por digest, SBOM/attestation e execução no SHA do RC;
2. runner de carga externo para separar servidor e gerador de carga;
3. `pg_stat_statements`, CPU/event-loop e traces correlacionados;
4. cenário com pelo menos dois tenants e prova de isolamento;
5. soak de duas horas, rede degradada/proxy TCP e budgets aprovados;
6. repetição no staging equivalente à produção.
