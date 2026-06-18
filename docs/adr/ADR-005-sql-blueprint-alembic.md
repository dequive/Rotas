# ADR-005 - SQL como Blueprint, Alembic como Verdade

## Estado

Aceite.

## Contexto

Documentos de engenharia contem SQL conceitual, mas migrations precisam ser incrementais e testaveis.

## Decisao

SQL em documentos e anexos e blueprint. A verdade de schema sera Alembic + modelos SQLAlchemy.

## Consequencias

- Nenhuma tabela entra sem migration.
- Alteracoes de schema devem ser revisadas.
- Migrations devem ser pequenas, rastreaveis e reversiveis quando possivel.

