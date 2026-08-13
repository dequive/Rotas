# PR17 — No demo fallback nas jornadas operacionais

Estado: **parcial local / NO-GO global**  
Data: 2026-08-10  
Branch: `codex/pr17-no-demo-runtime`  
Base: `0abd4d8` (PR16)

## Escopo executado

Foram removidos os fallbacks e datasets fictícios das jornadas operacionais não financeiras: torre de controlo, histórico de frota/viatura, combustível, operações administrativas, recepção e assinatura de evidências. Os estados de indisponibilidade e ausência de dados são agora explícitos e fail-closed.

O billing foi deliberadamente mantido inalterado, conforme instrução do produto. Por isso o gate global não pode ser declarado verde.

## Evidência local

- Gate estrutural não-billing: **verde** (`test:no-demo`: 4/4; `verify:no-demo:non-billing`: passed).
- Testes focados PR17: **10/10 passed** em 3 ficheiros.
- Suite Manager após correção dos bloqueios herdados: **15 ficheiros / 86 testes passed**.
- TypeScript após correção dos contratos Next16, Analytics, Sheet e detalhe da OS: **verde (`tsc --noEmit`)**.
- Build Manager no worktree com o junction local: **verde em Next 16.2.12 com Webpack**; o build por Turbopack nesse worktree continua condicionado pelo junction de `node_modules` do ambiente OneDrive.

### Revalidação limpa de 2026-08-13

Foi criado um clone temporário isolado e executado `npm ci`, confirmando a versão contratada pelo lockfile (`Next 14.2.35`) em vez da instalação Next16 exposta pelo junction do checkout principal. Nesse ambiente, os gates frontend equivalentes à CI ficaram verdes:

- BFF boundary: **9/9 testes**, 99 client roots, 121 módulos browser-reachable, 34 API routes e 0 violações.
- No-demo não-billing: **4/4 testes** e gate estrutural verde; continuam 12 violações congeladas no billing.
- Tipos OpenAPI Manager: **verde**.
- Manager: **15 ficheiros / 86 testes passed**.
- Driver: **5 ficheiros / 30 testes passed**.
- Typecheck de todos os workspaces: **verde**.
- Build Manager com Next 14.2.35: **verde**, 73 páginas geradas.
- Build Driver/PWA: **verde**, 1.805 módulos, service worker com 93 módulos e 6 entradas de precache.

Limite ambiental desta revalidação: a máquina local executou Node 24.16.0, enquanto o repositório e a CI declaram Node 20.x; a certificação final continua dependente da execução remota da CI.

## Gating e limites

- O gate completo permanece **fail-closed**, com **12 violações congeladas no billing** (`billing-api`, guards, faturação/rentabilidade, `.env.example` e configuração Playwright).
- A CI inclui os gates não-billing; a execução remota continua condicionada ao bloqueio de billing da conta GitHub.
- A base de dados original online não foi consultada, migrada, escrita ou sujeita a operações destrutivas.
- Não há certificação de staging/produção nem E2E live nesta etapa.

## Próxima etapa obrigatória

Resolver separadamente o billing (quando descongelado) e obter execução remota dos gates em Node 20 antes de promover PR17 para release.
