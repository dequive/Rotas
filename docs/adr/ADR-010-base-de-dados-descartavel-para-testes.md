# ADR-010 — Base de dados descartável e fail-closed para testes

## Estado

Aceite; implementação pendente como bloqueio C1-I0.

## Data

2026-08-22

## Contexto

`backend/tests/conftest.py` instancia `AsyncSessionLocal`, que usa diretamente
`DATABASE_URL`. A fixture não abre uma transação exterior com rollback nem
limpa os dados depois do teste. Vários services e chamadas ASGI executam
`commit`, portanto a suíte acumula tenants, viagens, paragens e outros registos
na base configurada.

Em 2026-08-22, a configuração mascarada apontava para
`postgresql+asyncpg://localhost:55432/rotas`. Uma consulta somente leitura
encontrou milhares de `trip_stops`, demonstrando que a base não é descartável
nem isolada por execução. Não foi provado que esses dados sejam produção, mas a
base `rotas` é a base operacional local e não pode ser tratada como sandbox.

Isto compromete repetibilidade, independência, concorrência e a validade da
evidência. Também cria risco de corrupção de uma cópia original/local.

## Decisão

1. Testes mutáveis backend usarão exclusivamente `TEST_DATABASE_URL`.
2. O bootstrap pytest falhará antes da coleção quando:
   - `TEST_DATABASE_URL` estiver ausente;
   - for igual a `DATABASE_URL`, `ADMIN_DATABASE_URL` ou
     `ALEMBIC_DATABASE_URL`;
   - o nome da base não corresponder ao padrão explícito de base descartável
     `rotas_test_*`;
   - o host não estiver numa allowlist de infraestrutura de teste.
3. Cada execução/worker receberá uma base própria criada de `template0`,
   migrada até `head` e removida no fim por um lifecycle seguro.
4. Falha de cleanup não autoriza reutilizar a base silenciosamente; a próxima
   execução deve criar outro nome e reportar o orphan para limpeza controlada.
5. Serviços podem continuar a fazer `commit`; o isolamento é garantido pela
   base efémera, não por mocks ou rollback frágil da fixture.
6. Dados já acumulados em `localhost:55432/rotas` não serão apagados
   automaticamente. Qualquer limpeza exige inventário, backup e autorização
   explícita do utilizador.
7. Até C1-I0 estar verde, nenhum agente executará testes que façam escrita na
   base. São permitidos lint, typecheck, geração estática e inspeções
   comprovadamente read-only.

## Alternativas consideradas

### Continuar a usar `DATABASE_URL`

Rejeitada: não existe isolamento e os commits atravessam a fixture.

### Rollback por teste na mesma base

Rejeitada como controlo principal: os services fazem commits internos, existem
clientes ASGI com sessões independentes e testes de concorrência/workers.

### SQLite em memória

Rejeitada: não prova PostgreSQL, RLS, locks, constraints, Alembic nem
concorrência reais.

### Base PostgreSQL efémera por execução/worker

Aceite: preserva semântica real e torna criação/destruição explícitas,
auditáveis e paralelizáveis.

## Consequências

- A suíte deixa de funcionar por acidente contra a base operacional.
- CI/local precisam de PostgreSQL e permissão controlada para criar bases de
  teste.
- O arranque fica ligeiramente mais lento, mas a evidência torna-se repetível.
- O baseline anterior de testes permanece evidência histórica; não certifica
  isolamento até C1-I0 ser implementado e a suíte repetida.
