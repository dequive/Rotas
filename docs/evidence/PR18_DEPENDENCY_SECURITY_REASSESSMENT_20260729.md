# PR-18 — Reavaliação de Segurança das Dependências

Data da evidência: 2026-07-29  
Estado: `blocked_upstream`  
Âmbito: grafo npm local válido; execução em Node 24, não no RC Node 20

## Resultado

PR-18 permanece bloqueado. A atualização válida reduziu a auditoria de
produção de quatro para três vulnerabilidades `high`, mas o Next estável
`16.2.12` continua a declarar e instalar:

- `next@16.2.12 -> postcss@8.4.31`;
- `next@16.2.12 -> sharp@0.34.5`.

As versões permanecem afetadas pelos advisories PostCSS e Sharp registados na
auditoria npm. Não existe `critical`, mas o critério do PR-18 exige também zero
`high`.

## Atualizações aceites

- Next `16.2.11 -> 16.2.12`, patch estável mais recente observado;
- PostCSS direto `8.5.15 -> 8.5.24`;
- `brace-expansion@5.0.7 -> 5.0.8`;
- cadeias `brace-expansion@2.1.x -> 2.1.3`.

O grafo final é estruturalmente válido:

```text
npm ls next postcss sharp brace-expansion --all
exit 0
```

## Override rejeitado

Foi ensaiada numa instalação limpa e isolada a substituição de PostCSS e Sharp
privados do Next por `8.5.24` e `0.35.3`.

O ensaio produziu `npm audit --omit=dev` com zero vulnerabilidades, mas
`npm ls` terminou com exit 1 e marcou ambos os pacotes como `invalid`, porque
não satisfaziam os ranges publicados pelo Next:

```text
postcss@8.5.24 invalid: "8.4.31" from node_modules/next
sharp@0.35.3 invalid: "^0.34.5" from node_modules/next
```

O override foi rejeitado e não integra o repositório. Auditoria verde sobre
uma árvore inválida não é aceite como mitigação.

## Auditoria final

```text
Produção:
  high: 3
  moderate: 0
  critical: 0

Grafo completo:
  high: 17
  moderate: 1
  critical: 0
```

As três entradas de produção são `next`, `postcss` e `sharp`, todas ligadas à
cadeia privada do Next. `brace-expansion` já não aparece na auditoria de
produção.

## Regressão executada

```text
Manager Vitest: 19 ficheiros, 89 passed
Driver Vitest: 5 ficheiros, 26 passed
Typecheck: Manager + Driver + http-contract verdes
Manager build: Next 16.2.12, 72 rotas
Driver build: 1.808 módulos + 93 módulos SW, 6 entradas precache
```

O build local usou Node 24 e reportou incompatibilidade com o engine
versionado `20.x`. A reprodução no Node 20 do CI e no SHA do RC continua
obrigatória.

## Critérios de desbloqueio

PR-18 só pode sair de `blocked_upstream` quando:

1. uma versão suportada do Next instalar PostCSS e Sharp corrigidos;
2. `npm ls` terminar com exit 0, sem `invalid`;
3. `npm audit --omit=dev` reportar zero `critical/high`;
4. a auditoria completa ficar sem `critical/high`, ou existir waiver formal
   com owner, prazo, exposição e compensating controls;
5. testes, typecheck e builds passarem no Node 20 e no mesmo SHA do RC.

G4 permanece vermelho e PR-26 continua bloqueado.
