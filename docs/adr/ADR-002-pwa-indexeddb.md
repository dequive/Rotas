# ADR-002 - PWA com IndexedDB

## Estado

Aceite.

## Contexto

Motoristas operam em ambientes de conectividade instavel. O app precisa funcionar sem internet e sincronizar depois.

## Decisao

O app motorista sera PWA React/Vite com IndexedDB via Dexie.js. SQLite nao entra no MVP.

## Consequencias

- Nao depende de app store.
- Funciona via browser mobile.
- Operacoes criticas gravam localmente antes de sincronizar.
- O sync precisa ser idempotente e resiliente.

