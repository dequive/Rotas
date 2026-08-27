# ROTAS — Modelo de Ameaças e Privacidade

Versão: `PR23-THREAT-MODEL-V1`  
Data: 2026-07-27  
Estado: baseline de engenharia; não certificada em produção  
Gate: G4 — vermelho

## 1. Decisão executiva

Este documento e o registo canónico
`infra/security/ROTAS_SECURITY_MODEL.json` estabelecem a baseline de segurança
e privacidade do ROTAS. A baseline é verificável em CI, mas **não fecha o
PR-23**: o pentest independente não foi executado, o release candidate ainda
não está em staging, o PR-18 mantém vulnerabilidades `high` e não existe
validação jurídica aprovada.

O modelo adopta as quatro perguntas de threat modeling da OWASP, categorias
STRIDE, OWASP ASVS 5.0.0 como referência de verificação e OWASP API Security
Top 10 2023 para abuso de APIs. Estas referências orientam a cobertura; não
constituem certificação.

## 2. Hierarquia SaaS obrigatória

```text
Operador ROTAS SaaS
└── Tenant independente
    ├── utilizadores, motoristas e trabalhadores do tenant
    └── clientes próprios do tenant
```

Um cliente do tenant não é outro tenant da plataforma. O tenant controla a
relação operacional com os seus clientes dentro da autorização e do contrato
aplicáveis. Nenhum identificador enviado pelo browser ou pelo dispositivo
substitui a identidade `tenant_id` derivada da autenticação.

Existem dois planos separados:

- control plane: operador ROTAS, subscrição, tenant, suporte e billing SaaS;
- data plane: ERP/TMS do tenant, incluindo os clientes próprios, finanças,
  stocks, oficina, frota, RH, documentos e BI.

Tokens, papéis, sessões e bases administrativas do control plane não podem ser
aceites implicitamente pelo data plane.

## 3. Sistema e fronteiras

O escopo inclui Manager/Next.js e o seu BFF same-origin, Driver PWA e dados
offline, FastAPI, PostgreSQL/RLS, Redis e workers, object storage, transactional
outbox, Governance Engine, email/messaging, observabilidade e backups.

As fronteiras canónicas estão no registo JSON:

- edge público;
- browser Manager e BFF;
- dispositivo Driver e armazenamento offline;
- API tenant-scoped;
- control plane da plataforma;
- PostgreSQL com RLS;
- Redis, jobs e caches;
- object storage;
- outbox e Governance;
- integrações externas;
- observabilidade;
- backup e restore.

O BI é read-derived e tenant-scoped. Dashboards, modelos ou recomendações não
podem escrever directamente nas tabelas operacionais; uma acção aceite volta
ao domínio como comando autenticado, autorizado, idempotente e auditado.

## 4. Método de risco

`risco = probabilidade (1..5) × impacto (1..5)`.

| Resultado | Classificação |
| ---: | --- |
| 1–4 | low |
| 5–9 | medium |
| 10–16 | high |
| 17–25 | critical |

Para G4 não é permitida aceitação de `high` ou `critical`. O registo começa
deliberadamente com todas as 16 ameaças como bloqueantes até que o RC seja
testado. Um controlo confirmado localmente reduz incerteza de engenharia, mas
não fecha o risco de implantação.

## 5. Resumo do registo

| Grupo | Riscos principais | Situação |
| --- | --- | --- |
| Tenancy e dados | IDOR/cross-tenant, RLS bypass, control-plane confused deputy | controlos locais; pentest e JIT support pendentes |
| Sessão e clientes | BFF/CSRF/XSS, perda do dispositivo Driver | fronteiras locais; DAST e real-device pendentes |
| Integridade | replay, sync, finanças, stock, oficina e Governance | cobertura parcial; inventário integral e fault injection pendentes |
| Ficheiros e integrações | object keys, malware, presign, SSRF e subprocessadores | isolamento/storage real e scanning pendentes |
| Privacidade | telemetry, retenção, DSAR, export, offboarding e backups | políticas/jornadas/parecer jurídico pendentes |
| Supply chain e disponibilidade | advisories, imagens, quotas, pool e DoS | PR-18 bloqueado; staging/load/soak pendentes |

O detalhe, owners, controlos, evidências e verificações exigidas está em
`infra/security/ROTAS_SECURITY_MODEL.json`.

## 6. Privacidade por desenho

### 6.1 Classes

- `public`: informação aprovada para publicação;
- `internal`: configuração e métricas agregadas sem dados de negócio;
- `confidential`: clientes do tenant, documentos comerciais, histórico de
  viatura e registos de trabalhadores;
- `restricted`: credenciais, payroll, dados bancários, documentos de
  identidade e localização precisa.

`restricted` exige mínimo privilégio, autenticação reforçada para operações
sensíveis, minimização por campo, auditoria de acesso e exclusão de payloads de
telemetria.

### 6.2 Ciclo de vida

Antes de produção, cada categoria necessita de finalidade, fundamento
validado, fonte, owner, consumidores, localização, subprocessador, retenção,
arquivo, excepção imutável e forma de eliminação. É obrigatório demonstrar:

1. acesso, correcção, exportação, restrição e eliminação tenant-scoped quando
   legalmente aplicável;
2. excepções documentadas para facturação, contabilidade, payroll, auditoria e
   segurança;
3. offboarding que trate PostgreSQL, Redis, browser/PWA, objectos, BI,
   observabilidade, réplicas e backups;
4. contratos e avaliação dos subprocessadores;
5. inexistência de dados pessoais reais em desenvolvimento local, fixtures e
   relatórios de carga.

Este documento não determina sozinho se ROTAS ou o tenant actua como
responsável ou operador por cada finalidade. Essa matriz depende do produto,
do contrato e da legislação aplicável e requer validação jurídica em
Moçambique.

## 7. Controlos locais confirmados e limites

Confirmados em código/testes locais:

- separação de papéis `rotas_app` NOBYPASSRLS e `rotas_admin`;
- startup de produção rejeita conexão aplicacional superuser/BYPASSRLS;
- escopos JWT de plataforma e tenant separados;
- RLS/FORCE RLS e testes cross-tenant;
- BFF same-origin e cookies HttpOnly, com gate estático contra tokens no
  browser;
- identidade offline por tenant/driver/sessão e limpeza fail-closed;
- idempotência e atomicidade em fluxos críticos cobertos;
- scrub de campos PII no Sentry e relatórios de performance sem Authorization;
- transactional outbox e replay operacional auditado;
- backup local cifrado com validações de restore.

Ainda não provado:

- comportamento no SHA exacto de um RC implantado;
- todos os endpoints, relações, objectos e jobs sob duas identidades tenant;
- JIT/break-glass de suporte com aprovação, motivo, expiração e revogação;
- bucket policies, malware scanning e criptografia/rotação reais;
- logs/traces/Sentry reais sem dados sensíveis;
- retenção, DSAR e offboarding ponta a ponta;
- resistência a abuso, SSRF, XSS, CSRF, request smuggling e DoS;
- fechamento dos advisories e verificação da supply chain.

## 8. Gate automatizado

Executar:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.validate_security_model
.\.venv\Scripts\python.exe -m pytest tests\test_security_model.py -q
```

O validador falha se a hierarquia SaaS for alterada, uma fronteira/ameaça/fluxo
desaparecer, o score não for reproduzível, um risco for pré-fechado, o pentest
for declarado sem evidência ou forem introduzidos padrões de segredo.

## 9. Critério de fecho PR-23

PR-23 só muda para concluído quando:

1. PR-18 tem zero vulnerabilidades `high/critical`;
2. PR-19 disponibiliza o RC em staging production-like, por SHA e digest;
3. existe autorização e Rules of Engagement assinada;
4. pentest independente cobre os papéis e superfícies do registo;
5. duas organizações tenant com identificadores sobrepostos provam
   isolamento na API, RLS, storage, cache, jobs, BI e exports;
6. não há findings `high/critical` abertos;
7. todas as correcções são repetidas pelo tester;
8. findings medium/low têm owner e data;
9. matriz jurídica/privacidade é aprovada;
10. relatório final liga tester, alvo, janela, SHA/digests, ferramentas,
    limitações, findings, reteste e decisão.

Até lá, PR-23 permanece `in_progress`, G4 permanece vermelho e o produto
continua `NO-GO` para produção.

