# Research Summary — ROTAS MVP
_Last updated: 2026-06-05_

---

## TL;DR

- **O offline-first promise não é entregável hoje.** A lógica Dexie.js + sync backend existe end-to-end, mas o driver PWA não tem Service Worker. O app não carrega offline, não instala, não sincroniza em background. É o gap de maior prioridade antes de qualquer deploy comercial.
- **O stack está correto e não deve mudar.** Todos os 5 gaps de integração (Workbox, Railway deploy, token refresh, R2 storage, PDF) têm soluções claras com libraries bem mantidas que se encaixam na arquitetura existente sem reescritas.
- **Há um CVE crítico ativo antes de qualquer usuário externo.** `python-jose` tem CVE-2025-61152 — tokens `alg=none` são aceites sem verificação de assinatura (auth bypass total). Migrar para `PyJWT >= 2.8` antes do primeiro utilizador real.
- **ROTAS é hoje uma ferramenta de recolha de dados, não uma plataforma de gestão.** As partes difíceis estão construídas (sync offline, ciclo de viagem, compliance, WACC combustível). O que falta é a camada que apresenta estes dados ao gestor: relatórios, KPIs, alertas de vencimento, manutenção preventiva.
- **O mercado moçambicano valida a direção do produto.** Nenhum concorrente identificado oferece SaaS de frota em português, sem hardware, para PMEs em Moçambique. Offline-first, compliance-gated e entrada manual são escolhas corretas para este mercado.

---

## Stack Recommendations

Todas as recomendações são aditivas ao stack confirmado. Não alterar o stack base.

| Gap | Recomendação | Versão | Confiança |
|-----|--------------|--------|-----------|
| Service Worker / PWA | `vite-plugin-pwa` + `workbox-background-sync`, estratégia `injectManifest` | vite-plugin-pwa v1.x | ALTA |
| Background jobs | ARQ (asyncio-native, usa Redis já provisionado) | Latest stable | ALTA |
| PDF generation (UTF-8) | `fpdf2` com DejaVuSans.ttf embutido | >= 2.8.7 | ALTA |
| File storage | `boto3` com endpoint R2 S3-compatible + presigned PUT/GET | >= 1.34 | ALTA |
| Token refresh | Access token em memória + HttpOnly cookie para refresh token + tabela de rotação | — | MÉDIA |
| Redis caching | `redis[asyncio]` — adicionar ao `pyproject.toml` (provisionado mas não instalado) | >= 5.0 | ALTA |
| JWT library | Migrar `python-jose` → `PyJWT >= 2.8` (CVEs ativos em python-jose) | >= 2.8 | ALTA |

**Gaps não resolvidos a verificar antes das fases de UI do manager:**
- Confirmar se `tailwind.config.*` existe em `apps/manager/` — shadcn/ui exige Tailwind mas não foi encontrado config no audit
- Fixar Node.js em 20 LTS via `"engines"` nos `package.json` antes do deploy Vercel

---

## Table Stakes vs Differentiators

### Table Stakes — deve funcionar ou o utilizador vai embora

| Feature | Status | Bloqueador? |
|---------|--------|-------------|
| Ciclo de viagem offline (partida → comprovante de descarga) | Backend construído; **PWA-01 ausente** | SIM — PWA-01 |
| Exportação de faturas PDF com UTF-8 português | Ausente (BILL-01) | SIM — antes do 1.º ciclo de faturamento |
| Exportação de faturas XLSX | Ausente (BILL-02) | SIM — antes do 1.º ciclo de faturamento |
| Bloqueio por documentos vencidos (viaturas + motoristas) | Lógica de bloqueio existe; **alertas proativos ausentes** | Médio |
| JWT com token refresh (access tokens 15 min) | Ausente (AUTH-01, AUTH-02) | SIM — requisito de segurança |
| Rate limiting em endpoints de auth | Ausente (SEC-03) | SIM — antes de produção |
| KPIs de gestão (custo, utilização, alertas) | **Gap maior** — dados existem, camada de agregação ausente | ALTO — valor central do produto |
| Manutenção preventiva programada | Ausente — oficina é apenas reativa | MÉDIO — operadores esperam esta feature |

### Differentiators — vantagem competitiva

| Feature | Força | Confiança |
|---------|-------|-----------|
| Ciclo de viagem offline completo no Android PWA (sem hardware) | Moat real vs Cartrack/MiX hardware-dependente | ALTA |
| Partidas bloqueadas por compliance (server + IndexedDB) | Mais seguro do que apenas alertar; raro em ferramentas PME | MÉDIA |
| SaaS em português para compliance moçambicano (INATTER, Guia de Transporte) | Nenhum concorrente direto identificado | MÉDIA |
| Custo de combustível por média ponderada | Incomum em ferramentas SME de frota; precisão de faturamento | MÉDIA |

### Anti-features — não construir no MVP

GPS streaming em tempo real, dashcam/vídeo telematics, otimização de rotas por IA, app nativa iOS/Android, integração ERP, integração de cartão de combustível, módulo de folha de pagamento de motoristas.

---

## Architecture Decisions

**Resolução de conflitos de sync — Versionamento server-authoritative**
Adicionar coluna `server_version` inteiro nas entidades sincronizáveis. Cliente envia `base_version` no payload do batch. Servidor ganha em conflitos de mesmo campo. Operações append-only (paradas, respostas de checklist, comprovantes de descarga) são conflict-free por design. CRDTs não são apropriados para este domínio single-writer.

**Redis Caching — Cache-aside com chaves namespace por tenant**
Padrão: `ct:kpis:{tenant_id}`, TTL 60s para KPIs, 30s para alertas. Usar `NX + EX` lock para prevenir cache stampede. **Regra crítica: toda chave Redis deve incluir `tenant_id`** — omitir causa cache poisoning cross-tenant (dados financeiros visíveis entre tenants).

**PostgreSQL RLS — Defense-in-depth (não substitui filtros na aplicação)**
Adicionar como segunda camada via migração Alembic. Usar `contextvars` para contexto de tenant thread-safe + SQLAlchemy `after_begin` event listener. Filtros `tenant_id` na aplicação ficam. Escrever testes de regressão cross-tenant ANTES de iniciar CT-01 — a reescrita de queries é o momento de maior risco.

**Background Jobs — ARQ em vez de Celery ou FastAPI BackgroundTasks**
ARQ usa o Redis já provisionado, é asyncio-nativo e suporta retry/persistência. Deploy como processo separado no Railway. Usar ARQ para: geração de alertas, exportação PDF/XLSX, compliance checks agendados, qualquer tarefa > 500ms.

**Fix N+1 — Eager loading explícito**
Substituir ~38 queries sequenciais no Control Tower: `joinedload` para many-to-one (viagem → viatura/motorista), `selectinload` para one-to-many (viagem → paradas), `func.count()` SQL para KPIs escalares. Resultado esperado: 38 queries → 4-6 queries. Definir `lazy="raise"` nas relações SQLAlchemy em desenvolvimento para apanhar lazy loads acidentais.

**Service Worker — Estratégia `injectManifest`**
`src/sw.ts` personalizado é necessário para expressar a lógica de background sync queue para `POST /sync/batch` offline. Dexie.js persiste registos de domínio; Workbox background sync flush as chamadas de rede quando a conectividade retorna. Ambas as camadas são necessárias e complementares.

---

## Watch Out For

Ordenado por severidade — os pitfalls com maior probabilidade de causar incidentes em produção.

**1. CVE-2025-61152 em `python-jose` — Auth Bypass Completo (CRÍTICO)**
Tokens `alg=none` são aceites sem verificação de assinatura. Qualquer endpoint autenticado é acessível sem credenciais. Resolver antes de qualquer deploy com utilizadores externos. Fix: migrar para `PyJWT >= 2.8`.

**2. Filtro `tenant_id` ausente = Fuga silenciosa de dados cross-tenant (CRÍTICO)**
Isolamento apenas na aplicação significa que uma query sem `.where(Model.tenant_id == tenant_id)` retorna dados de todos os tenants com HTTP 200. A fase CT-01 (reescrita de queries) é a janela de maior risco. Prevenção: testes de regressão cross-tenant antes de CT-01; RLS como segunda camada.

**3. Service Worker cacheado com build quebrado — sem escape (ALTO)**
Uma vez instalado, um SW com build defeituoso é servido pelo cache para cada motorista que retorna — sem possibilidade de fix pelo servidor. Em Android de baixo custo em Moçambique, "limpar dados do site" é inacessível para a maioria dos motoristas. Prevenção: `Cache-Control: no-store` no `sw.js`; botão visível "verificar atualizações".

**4. Falha parcial no batch sync deixa a fila inconsistente (ALTO)**
Se o processamento do batch não estiver em transação e o servidor falhar a meio, algumas operações commitam e outras não. O motorista perde dados ou cria duplicados. Prevenção: códigos de status por item na resposta do batch; `sync.ts` deve processar resultados por item, não apenas o HTTP status top-level.

**5. `ENVIRONMENT` sem definição em produção ativa bypass de test-token (ALTO)**
Se `ENVIRONMENT` não for explicitamente definida no Railway/Render, o bypass `test-token` permanece ativo, CORS fica permissivo e stack traces aparecem nas respostas da API. Prevenção: `ENVIRONMENT=production` é a primeira variável a definir em qualquer deploy.

---

## Roadmap Implications

**4 fases com dependência sequencial estrita nas primeiras duas:**

**Fase 1 — Segurança + Fundação de Deploy**
CVE auth bypass e JWT secret hardcoded bloqueiam tudo. Nada mais importa se o auth está comprometido e o backend não consegue fazer deploy.
Cobre: SEC-01 a SEC-04, AUTH-01 a AUTH-03, DEPLOY-01 a DEPLOY-04, migração `python-jose` → `PyJWT`, testes de regressão cross-tenant, `ENVIRONMENT=production` como startup guard.

**Fase 2 — Completar PWA Offline-First**
A promessa central do produto. O Service Worker é a peça que falta para o driver app ser instalável e funcionar offline. Requer field testing em hardware Android real antes de qualquer motorista usar o sistema.
Cobre: PWA-01 a PWA-03, AUTH-04 (sync `update` para todos os entity types), processamento de resultados por item no batch, timestamps duplos para clock skew, UI de resolução de conflitos para motoristas.

**Fase 3 — Dashboard do Gestor + Camada de Reporting**
Transforma ROTAS de ferramenta de recolha em plataforma de gestão operacional. CT-01/CT-02/CT-03 são os enablers técnicos; relatórios, alertas de vencimento e exportação de faturamento são os entregáveis de produto.
Cobre: CT-01 (otimização de queries + RLS), CT-02 (Redis caching + ARQ worker), CT-03 (paginação), BILL-01 (PDF com fpdf2), BILL-02 (XLSX), BILL-03 (waiver margem negativa), alertas de vencimento de documentos, custo-por-km/viatura, dashboard de utilização de frota.

**Fase 4 — Hardening em Produção + Preparação para Escala**
Itens que importam em escala multi-tenant mas não são bloqueadores de lançamento.
Cobre: scheduler de manutenção preventiva (triggers por odômetro/calendário → work orders automáticas), scorecard de motoristas, migração `float` → `Numeric(10,2)` com backfill faseado, config Gunicorn multi-worker, composite index audit com `tenant_id` como leading column.

**Dependência entre fases:** Fase 1 → Fase 2 → Fase 3 → Fase 4. O planeamento da Fase 3 pode começar durante os testes finais da Fase 2.

---

## Confidence Assessment

| Área | Confiança | Base |
|------|-----------|------|
| Stack (gaps de integração) | ALTA | 5 soluções verificadas em docs oficiais 2026-06-04 |
| Features (table stakes) | MÉDIA-ALTA | Pesquisa de mercado África sólida; dados Moçambique-específicos limitados |
| Arquitectura (padrões) | MÉDIA-ALTA | Redis, RLS, ARQ, N+1 de docs oficiais + artigos 2025-2026 |
| Pitfalls (severidades) | ALTA | CVEs de bases de vulnerabilidades; deploy pitfalls de docs oficiais Railway/Render |

**Gaps que requerem validação externa:**
1. Requisitos fiscais (e-fatura / registo AT em Moçambique) — revisão legal antes de BILL-01 chegar a clientes pagantes
2. Canal de notificação (email vs WhatsApp Business API vs push) — entrevista a operadores antes de construir a infraestrutura de alertas
3. Compatibilidade de Background Sync em hardware Android low-cost — requer field testing real
4. Maturidade do mercado — nenhum concorrente SaaS direto encontrado; pode indicar oportunidade ou mercado pré-SaaS
