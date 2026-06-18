# ADR-001 - Monolito Modular

## Estado

Aceite.

## Contexto

O ROTAS precisa validar rapidamente o MVP sem carregar complexidade operacional de microservicos. O produto ainda esta a estabilizar regras de dominio: viagens, carga, documentos, offline sync e cobranca.

## Decisao

O MVP sera um monolito FastAPI modular, com deploy unico e separacao interna por dominio.

## Consequencias

- Menos infraestrutura.
- Mais velocidade de entrega.
- Menos latencia entre modulos.
- Fronteiras internas devem ser respeitadas para futura extraccao, se necessario.

