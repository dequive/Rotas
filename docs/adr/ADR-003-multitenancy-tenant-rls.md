# ADR-003 - Multi-tenancy com tenant_id e RLS

## Estado

Aceite.

## Contexto

ROTAS e SaaS multi-cliente. Dados de uma frota nao podem vazar para outra.

## Decisao

Todas as tabelas operacionais terao `tenant_id`. O service layer sempre filtra por tenant. PostgreSQL RLS sera defesa adicional.

## Consequencias

- Testes de isolamento por tenant sao obrigatorios.
- Frontend nao escolhe `tenant_id` livremente.
- RLS nao substitui verificacao na aplicacao.

