# Evidência C2 — Driver Android no produto fixo

- Data: 2026-08-26
- Produto: `a978229` (`ae1ede2` backend + `a978229` PWA)
- Documentação anterior: `58cdd5d`
- Dispositivo: Redmi 12, Android 15
- Aplicação: WebAPK `org.chromium.webapk.a6b269eaf4d1f3b17_v2`
- Bundle: `/assets/index-GP13naLz.js`
- Decisão global: `NO-GO`

## Integridade local

- backend em base efémera `template0 -> rec16`: `1010/1010`;
- Ruff: verde;
- Pyright: `0 errors, 0 warnings, 0 informations`;
- Driver: `67/67`, typecheck, build `1806/94/6`, E2E `7/7`;
- Manager: `128/128`, typecheck e build de 74 páginas;
- cliente OpenAPI: check sem drift;
- `git diff --check`: verde antes dos commits.

O build reproduziu `Access is denied` quando o Vite compilava a configuração
no OneDrive. Um teste RED passou a exigir `configLoader native` também no
build; o GREEN recompilou o mesmo bundle `index-GP13naLz.js`.

## Prova física no artefacto

1. O WebAPK atualizou e ficou com Service Worker ativo/controlador, sem worker
   em espera e sem JavaScript antigo no runtime cache.
2. Pairing administrativo real respondeu `200`; código, tokens e device id não
   foram impressos.
3. O motorista viu a viagem atribuída `Maputo -> Beira` entregue, com Load
   Permit, manifesto e guia de transporte, sem ações mutáveis.
4. Com reverses 4173/8000 removidos e as portas recusadas no Redmi, `force-stop`
   seguido de abertura recuperou shell/sessão pelo Service Worker e lista,
   detalhe e documentos pelo Dexie, marcados como guardados/somente leitura.
5. Restaurados apenas 4173/8000, viagens e documentos reconciliaram com `200`
   e os avisos stale desapareceram.
6. Na primeira passagem do mesmo bundle, a expiração natural produziu
   `GET trips 401 -> POST refresh 200 -> GET trips 200`; comparação apenas em
   memória confirmou substituição de access e refresh, mantendo sessão/viagem.
7. Depois dos commits, backend e preview foram reiniciados a partir do produto
   `a978229`. Cold start com API bloqueada voltou a preservar sessão, access
   expirado e refresh presente. O backend registou `GET 401`, `POST refresh 200`
   e `GET 200`; o novo access expirava 15 minutos depois e a viagem permaneceu
   visível. O bundle permaneceu `index-GP13naLz.js`.

## Limite da conclusão

C2 fica fechado como implementação validada localmente e em Android físico no
conteúdo do produto `a978229`. Isto não equivale a CI, staging, piloto ou
release certification. Actions imutáveis, supply chain, CI executada, revisão,
staging e RC integrado continuam pendentes; a decisão global permanece
`NO-GO`.
