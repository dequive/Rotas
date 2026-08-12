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
- Build Webpack: compilação concluída, mas a verificação Next falha no contrato Next16 de `searchParams` em `rh/processamento/page.ts`; Turbopack também encontra o junction de `node_modules` do ambiente OneDrive.

## Gating e limites

- O gate completo permanece **fail-closed**, com **12 violações congeladas no billing** (`billing-api`, guards, faturação/rentabilidade, `.env.example` e configuração Playwright).
- A CI inclui os gates não-billing; a execução remota continua condicionada ao bloqueio de billing da conta GitHub.
- A base de dados original online não foi consultada, migrada, escrita ou sujeita a operações destrutivas.
- Não há certificação de staging/produção nem E2E live nesta etapa.

## Próxima etapa obrigatória

Resolver separadamente o billing (quando descongelado), corrigir o bloqueio de build Next16/ambiente OneDrive e executar os gates completos em CI antes de promover PR17 para release.
