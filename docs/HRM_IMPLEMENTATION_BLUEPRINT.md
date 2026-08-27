# Blueprint de Implementação — HRM ROTAS

Versão: 2.0

Data: 2026-07-29

Estado: desenho técnico enterprise para implementação; não implementado nem
certificado, pendente de validação do operating model de RH

Relacionados: `docs/PRD_HRM_ROTAS.md` e
`docs/ROTAS_MASTER_DELIVERY_PLAN.md`

## 1. Decisão

Este documento transforma o PRD do HRM numa implementação executável: fronteiras
de código, modelo físico, contratos, segurança, motor de payroll, integrações,
migração, testes, operação e sequência de entrega.

O HRM será implementado no monólito modular FastAPI actual, com ownership de
dados, portas tipadas e eventos que permitam extracção futura. É o sistema
corporativo de pessoas do tenant, dirigido por RH; TMS e Oficina são integrações
operacionais, não o eixo da arquitectura.

O módulo legado `backend/app/modules/hr` será fonte de migração e compatibilidade,
não a fundação do novo payroll. O novo boundary nasce em
`backend/app/modules/hrm`, com tabelas prefixadas por `hr_` e API
`/api/v1/hrm`.

### 1.1 Resultado integral

- pessoa, worker, vínculo, posição e remuneração modelados separadamente;
- workforce strategy, positions, headcount, skills e custo planeados;
- recrutamento, candidate experience, oferta e onboarding;
- performance, learning, carreira, mobilidade e sucessão;
- total rewards, benefícios e employee experience;
- HR service delivery, relações laborais, engagement, saúde e segurança;
- estado laboral e salarial reconstruível em qualquer data;
- disponibilidade operacional explicável para TMS e Oficina;
- payroll determinístico, reproduzível e auditável;
- segregação entre preparação, validação, aprovação, posting e pagamento;
- reconciliação payroll-ledger-bank;
- protecção de PII e salário abaixo da API;
- migração sem pressupostos silenciosos;
- SLOs, runbooks, DR e evidência de promoção.

### 1.2 Não-objectivos iniciais

- código Python, SQL, JavaScript ou expressões arbitrárias em regras;
- identidade humana global inferida entre tenants;
- factos operacionais convertidos directamente em remuneração;
- IA a tomar decisões laborais adversas;
- conformidade legal declarada apenas porque uma fórmula existe;
- substituição dos módulos de identity, accounting ou treasury.

### 1.3 Estratégia build, buy e integrate

ROTAS deve construir o modelo canónico, workflows, authorization, temporalidade,
payroll ledger, workspaces e contratos. Deve permitir adapters para:

- job boards, background checks e assessments;
- assinatura electrónica;
- conteúdo/LMS SCORM ou xAPI;
- providers de benefícios;
- hardware de ponto;
- bancos, AT e INSS;
- medicina ocupacional e fornecedores de wellbeing.

Um provider não se torna fonte de verdade por integração. O adapter declara
ownership, finalidade, dados mínimos, consentimento/base aplicável, residency,
retenção, SLA, exportabilidade, webhook security, reconciliação e exit plan.

## 2. Gap real

O scaffold actual mistura pessoa, colaborador, vínculo, cargo, departamento,
salário e parâmetros fiscais mutáveis. Também existem conceitos dispersos:

- `Driver` contém dados laborais/documentais orientados à operação;
- a Oficina imputa mão-de-obra por `user_id`;
- availability compõe Driver, veículo, viagem, Oficina, HOS e waivers;
- o cliente Manager expõe banco e salário no DTO genérico de employee;
- a geração actual pode criar integração contabilística enquanto a folha ainda
  está em draft.

Logo, a implementação é uma migração expand/contract para um modelo canónico,
não um refactor cosmético do scaffold.

## 3. Invariantes

1. Toda a linha de negócio possui `tenant_id`.
2. Entidade legal e âmbito organizacional são explícitos.
3. Person, Worker, Employment, Position e User são entidades distintas.
4. Condições laborais e salariais são versões temporais.
5. TMS e Oficina mantêm ownership dos seus factos operacionais.
6. Payroll fechado é imutável; correcção é ajuste/suplemento referenciado.
7. Diário contabilístico só nasce depois da aprovação final.
8. Escritas financeiras têm idempotência permanente e unicidade de domínio.
9. Auditoria não replica PII ou salário em claro.
10. BI e IA são read-derived; uma recomendação aceite volta como comando.
11. Regras legais têm fonte, versão, vigência, owner e validação externa.

## 4. Arquitectura lógica

```text
Manager BFF / Employee Self-Service
                 |
          /api/v1/hrm
                 |
     application commands/queries
          /       |        \
     domain     ports     policies
        |          |          |
 repositories  adapters   rule engine
        |          |          |
 PostgreSQL   TMS/Oficina  payroll snapshots
        |
 transactional outbox -> inboxes -> projections/ERP/notifications
```

### 4.1 Pacotes

```text
backend/app/modules/hrm/
  api/{organization,people,planning,recruiting,journeys,employment}.py
  api/{rewards,time,leave,learning,performance,career,succession}.py
  api/{service_delivery,relations,safety,engagement,payroll,workspaces}.py
  domain/{entities,value_objects,states,policies,events,errors}.py
  application/{commands,queries,handlers,ports,authorization}.py
  infrastructure/{models,repositories,rule_engine,documents,outbox,inbox}.py
  integrations/{identity,tms,workshop,accounting,treasury,benefits,learning}.py
  projections/{availability,workforce_cost,talent,people_kpis,iso30414}.py
```

Regras:

- `domain` não importa FastAPI, SQLAlchemy, Redis ou HTTP;
- `application` orquestra casos de uso por portas tipadas;
- `api` traduz autenticação, DTOs, comandos, resultados e erros;
- integrações não importam ORM de outros módulos;
- a transacção pertence ao handler; serviços internos não fazem commit autónomo;
- efeitos externos saem por outbox na mesma transacção;
- analytics não escreve no núcleo transaccional.

### 4.2 PostgreSQL, tenancy e temporalidade

Na primeira fase, as tabelas ficam em `public` com prefixo `hr_`, reutilizando
Alembic, sessões e RLS actuais. A fronteira é garantida por ownership e contratos.

Todas as tabelas tenant-scoped exigem:

- `tenant_id UUID NOT NULL`;
- `ENABLE/FORCE ROW LEVEL SECURITY`;
- políticas `USING` e `WITH CHECK`;
- testes com a role operacional `NOBYPASSRLS`;
- `UNIQUE (tenant_id, id)` nos pais;
- foreign keys compostas `(tenant_id, parent_id)` nos filhos;
- índices iniciados por tenant nos caminhos reais.

Períodos efectivos usam `daterange` `[início, fim)`; intervalos intradiários usam
`tstzrange` ou `TIMESTAMPTZ`. Constraints GiST com `btree_gist` impedem
sobreposição de:

- termos do vínculo;
- versões de compensação;
- ocupação exclusiva de posição;
- ligações worker-user e worker-driver;
- turnos incompatíveis;
- rulesets activos no mesmo âmbito.

Aggregates concorrentes usam `lock_version`; workflows financeiros acrescentam
`SELECT FOR UPDATE`. Instantes são UTC, mas calendário, período e ponto guardam
timezone IANA. Dinheiro é `NUMERIC(19,4)` + moeda ISO 4217, nunca `float`.

## 5. Modelo físico

### 5.1 Organização, pessoa e vínculo

ERP-03 fornece `legal_entities`, `branches`, `cost_centers` e `org_units`.

| Tabela HRM | Responsabilidade |
|---|---|
| `hr_people` | identidade humana tenant-scoped |
| `hr_person_identifiers` | NUIT, BI/passaporte protegidos |
| `hr_person_contacts` | contactos classificados |
| `hr_worker_profiles` | participação na força de trabalho |
| `hr_employments` | vínculo com a entidade empregadora |
| `hr_employment_terms` | condições contratuais temporais |
| `hr_job_families`, `hr_job_profiles` | carreira, função e requisitos |
| `hr_positions` | cadeira/vaga orçamentada |
| `hr_position_assignments` | ocupação temporal |
| `hr_worker_user_links` | ligação à identidade autenticada |
| `hr_worker_driver_links` | ligação ao perfil operacional |
| `hr_employment_timeline` | factos do lifecycle e proveniência |

`hr_people` não contém salário, função, departamento, férias ou credenciais.
Listagens comuns usam uma projecção de baixo privilégio.

### 5.2 Compensação e lifecycle

| Tabela | Responsabilidade |
|---|---|
| `hr_compensation_packages` | aggregate estável por vínculo |
| `hr_compensation_versions` | versão aprovada e effective-dated |
| `hr_compensation_components` | base, subsídio, benefício ou desconto |
| `hr_workflow_approvals` | maker-checker reutilizável |
| `hr_contract_documents` | contrato e evidência assinada |
| `hr_offboarding_cases`, `hr_offboarding_tasks` | saída e fecho de obrigações |

Alterar remuneração cria nova versão `DRAFT`; activação exige período válido,
autorização de campo, maker-checker, motivo, evidência e evento sem valores em
claro. Uma versão activa é imutável.

### 5.3 Competências e elegibilidade

Criar `hr_skills`, `hr_worker_skills`, `hr_certification_types`,
`hr_certifications`, `hr_job_skill_requirements` e
`hr_operational_requirements`.

Certificações seguem `PENDING_VERIFICATION -> VALID -> EXPIRING -> EXPIRED`, com
`SUSPENDED` e `REVOKED`. Expiração produz factor de indisponibilidade; não altera
silenciosamente Driver.

### 5.4 Tempo, ponto, férias e disponibilidade

Criar:

- `hr_calendars`, `hr_calendar_days`;
- `hr_shift_templates`, `hr_shift_assignments`;
- `hr_attendance_devices`, `hr_attendance_events`;
- `hr_attendance_corrections`;
- `hr_timesheets`, `hr_timesheet_lines`;
- `hr_leave_types`, `hr_leave_policies`;
- `hr_leave_accounts`, `hr_leave_ledger`;
- `hr_leave_requests`, `hr_leave_approvals`;
- `hr_availability_projections`.

Ponto é append-only. O cliente offline envia `device_id`, `device_event_id`,
instante local, instante recebido, timezone, contador monotónico, assinatura e
qualidade de localização. A unique `(tenant_id, device_id, device_event_id)`
torna replay idempotente. Correcções referenciam o evento original.

Férias usam ledger de movimentos, não um saldo mutável. Availability continua
fachada operacional e compõe:

```text
factor HR (vínculo + escala + ausência + certificação)
+ factor TMS (viagem + HOS + licença operacional)
+ factor Oficina (tarefa + bloqueio técnico)
+ waiver autorizado
= decisão explicável
```

### 5.5 Documentos

O serviço de ficheiros ganha classificação, finalidade, retenção, legal hold,
scan de malware, versão de chave, cadeia de versões e auditoria de leitura.
Estados: `QUARANTINED`, `CLEAN`, `REJECTED`, `DELETED_BY_POLICY`. Downloads usam
URL curta só depois de autorização e estado `CLEAN`.

### 5.6 Planeamento, recrutamento e journeys

| Contexto | Tabelas principais |
|---|---|
| workforce planning | `hr_workforce_plans`, `hr_workforce_plan_versions`, `hr_workforce_scenarios`, `hr_workforce_assumptions`, `hr_position_budgets`, `hr_workforce_demands` |
| recruiting | `hr_job_requisitions`, `hr_requisition_approvals`, `hr_job_postings`, `hr_candidates`, `hr_candidate_consents`, `hr_applications`, `hr_application_stage_events` |
| assessment | `hr_interviews`, `hr_interview_panels`, `hr_scorecards`, `hr_scorecard_responses`, `hr_assessments` |
| offer | `hr_offers`, `hr_offer_versions`, `hr_offer_approvals` |
| journeys | `hr_journey_templates`, `hr_journey_template_versions`, `hr_journey_instances`, `hr_journey_tasks`, `hr_journey_dependencies`, `hr_journey_evidence` |

Plano, forecast, cenário e realizado são distintos. Requisition exige
posição/budget ou override aprovado. Candidate PII tem vault e retenção próprios;
só uma oferta aceite inicia conversão idempotente para pre-hire/person.

```text
REQUISITION: DRAFT -> APPROVED -> OPEN -> ON_HOLD -> FILLED/CANCELLED
APPLICATION: APPLIED -> SCREENING -> INTERVIEW -> ASSESSMENT
             -> OFFER -> HIRED | REJECTED | WITHDRAWN
OFFER: DRAFT -> APPROVED -> SENT -> ACCEPTED/DECLINED/EXPIRED/RESCINDED
```

Journeys coordenam HR, manager, worker, IAM, Assets, Facilities, Safety, Learning
e Payroll por adapters. Cada tarefa declara owner, dependência, SLA, evidência e
escalonamento; HRM não duplica os activos ou as contas.

### 5.7 Learning, performance, carreira e sucessão

| Contexto | Tabelas principais |
|---|---|
| learning | `hr_learning_items`, `hr_learning_versions`, `hr_learning_sessions`, `hr_enrollments`, `hr_learning_completions`, `hr_curricula`, `hr_development_plans` |
| goals/feedback | `hr_goal_cycles`, `hr_goals`, `hr_goal_alignments`, `hr_checkins`, `hr_feedback_requests`, `hr_feedback_responses`, `hr_recognition_events` |
| performance | `hr_review_cycles`, `hr_reviews`, `hr_review_sections`, `hr_calibration_sessions`, `hr_calibration_changes`, `hr_review_appeals` |
| career | `hr_career_paths`, `hr_career_steps`, `hr_career_preferences`, `hr_internal_opportunities`, `hr_mobility_applications` |
| succession | `hr_critical_positions`, `hr_succession_plans`, `hr_successor_candidates`, `hr_readiness_assessments`, `hr_talent_reviews` |

Review congela template, escala e população. Calibration preserva valor original,
mudança, actor e razão. Performance, potencial, skill e readiness são conceitos
distintos. SCORM/xAPI e conteúdo externo entram por adapter; não se constrói um
authoring studio.

### 5.8 Total rewards, benefícios e total workforce

Criar `hr_pay_structures`, `hr_pay_grades`, `hr_salary_ranges`,
`hr_compensation_cycles`, `hr_compensation_cycle_budgets`,
`hr_compensation_proposals`, `hr_reward_statements`, `hr_benefit_plans`,
`hr_benefit_plan_versions`, `hr_benefit_eligibility_rules`,
`hr_benefit_enrollments`, `hr_dependents`, `hr_beneficiaries`,
`hr_contingent_engagements`, `hr_agencies`, `hr_supplier_worker_links` e
`hr_project_assignments`.

Compensation planning gera uma versão aprovada; payroll apenas a executa.
Benefícios usam elegibilidade effective-dated. Contractors, agência, trainees e
interns partilham access/safety/time/learning quando aplicável, mas não são
classificados automaticamente como employees nem entram automaticamente em
payroll.

### 5.9 HR Service Delivery, engagement, ER e OHS

| Vault | Tabelas principais |
|---|---|
| service delivery | `hr_service_catalog_items`, `hr_service_requests`, `hr_cases`, `hr_case_tasks`, `hr_case_participants`, `hr_case_sla_events`, `hr_knowledge_articles`, `hr_knowledge_versions` |
| engagement | `hr_survey_campaigns`, `hr_survey_questions`, `hr_survey_responses`, `hr_survey_cohort_results`, `hr_action_plans` |
| employee relations | `hr_er_cases`, `hr_er_allegations`, `hr_er_parties`, `hr_er_interviews`, `hr_er_evidence`, `hr_er_actions`, `hr_er_appeals` |
| labour relations | `hr_collective_agreements`, `hr_worker_representatives`, `hr_consultation_events` |
| safety | `hr_hazards`, `hr_risk_assessments`, `hr_safety_incidents`, `hr_safety_investigations`, `hr_corrective_actions` |
| occupational health | `hr_fitness_assessments`, `hr_accommodations`, `hr_return_to_work_cases` |

Casos têm COE, confidentiality tier, assignment group, SLA e related journey.
Engagement anónimo publica apenas coortes acima do limiar. ER, denúncia e medical
usam repositories, capabilities, chaves e access logs segregados. O core recebe
apenas o outcome operacional mínimo, nunca diagnóstico ou narrativa.

## 6. Payroll determinístico

### 6.1 Tabelas

| Grupo | Tabelas |
|---|---|
| jurisdição | `hr_jurisdiction_packs`, `hr_jurisdiction_pack_versions` |
| regras | `hr_payroll_rule_sets`, `hr_payroll_rule_versions`, `hr_rate_tables`, `hr_rate_table_rows` |
| calendário | `hr_payroll_calendars`, `hr_payroll_periods`, `hr_payroll_codes` |
| execução | `hr_payroll_runs`, `hr_payroll_run_inputs`, `hr_payroll_calculations` |
| memória | `hr_payroll_lines`, `hr_payroll_calculation_steps` |
| controlo | `hr_payroll_approvals`, `hr_payroll_adjustments`, `hr_payroll_reconciliations` |
| saída | `hr_payroll_postings`, `hr_payroll_payment_batches`, `hr_payroll_payment_items` |
| legal | `hr_statutory_submissions` e payslips |

### 6.2 Kernel

```text
calculate(
  frozen_worker_input,
  approved_rule_set,
  approved_rate_tables,
  calculation_context
) -> calculation_result + calculation_steps
```

O kernel não lê DB, chama HTTP, consulta relógio, usa aleatoriedade ou muta
estado. Inputs guardam source type/id/version, data efectiva, elegibilidade e
aprovação. Decimais são strings canónicas no snapshot. Snapshot e resultado são
canonicalizados e hashed com versões de motor, ruleset e tabelas.

O mesmo snapshot na mesma versão do motor deve produzir o mesmo hash. Divergência
bloqueia aprovação.

### 6.3 DSL segura

Usar AST JSON tipado e versionado. Operações permitidas: referências declaradas,
aritmética decimal, `min/max/clamp`, comparação, `if`, lookup versionado,
acumuladores explícitos e rounding declarado.

Rejeitar referência circular, divisão possível por zero, input desconhecido,
unidades incompatíveis, output sem payroll code e dependência não aprovada. Não
usar `eval`, código do tenant ou SQL livre.

Rulesets seguem:

```text
DRAFT -> VALIDATED -> APPROVED -> ACTIVE -> RETIRED
```

### 6.4 FSM da folha

```text
OPEN -> INPUTS_LOCKED -> CALCULATED -> VALIDATED -> APPROVED
     -> POSTED -> PAYMENT_PENDING -> PAID -> CLOSED
```

Invariantes:

- uma run regular por tenant, entidade, calendário e período;
- suplemento referencia a run de origem;
- maker não aprova o seu próprio input sensível;
- aprovação guarda hashes exactos;
- posting requer `APPROVED`;
- payment requer posting reconciliável;
- `PAID` requer confirmação de tesouraria/banco;
- `CLOSED` requer reconciliação sem diferença não aprovada;
- uma run fechada nunca reabre.

Cada linha guarda input e proveniência, regra/versão/passo, base, taxa, valor
pré/pós-rounding, acumuladores e output. O payslip explica essa memória, mas não
a substitui.

### 6.5 Idempotência, ledger e banco

Comandos financeiros exigem `Idempotency-Key`. A chave é persistida com actor,
tenant, endpoint e request hash; reutilização com payload diferente falha. Não
depende apenas de TTL.

Unicidade de domínio cobre run por período, cálculo por vínculo, posting por
source/version, item por batch e submissão por obrigação/período.

O adapter contabilístico recebe, apenas após aprovação, source key, entidade
legal, período, dimensões, linhas balanceadas e hash. ERP-09 deve rejeitar source
key igual com conteúdo diferente. Treasury recebe apenas os dados necessários,
e cada item é reconciliado com folha e diário. ERP-09/10 são gates de promoção.

## 7. API e autorização

### 7.1 Convenções

- `/api/v1/hrm`;
- DTOs distintos para create/update/list/detail/self;
- paginação cursor-based;
- filtros `effective_on` e `as_of`;
- erros estáveis em `application/problem+json`;
- `Idempotency-Key` em comandos;
- `If-Match` em alterações concorrentes;
- OpenAPI e TypeScript gerados em CI;
- PII nunca expandida por `include=*`.

### 7.2 Recursos e comandos

```text
/organization/positions
/workforce-plans
/workforce-scenarios
/job-requisitions
/candidates
/applications
/offers
/journeys
/people
/workers
/workers/{id}/employments
/employments/{id}/terms
/employments/{id}/compensation-versions
/workers/{id}/skills
/workers/{id}/certifications
/learning-items
/learning-enrollments
/goal-cycles
/performance-reviews
/calibration-sessions
/career-paths
/internal-opportunities
/succession-plans
/compensation-cycles
/benefit-plans
/shifts
/attendance-events
/timesheets
/leave-requests
/availability-decisions
/payroll/rule-sets
/payroll/periods
/payroll/runs
/payroll/runs/{id}:lock-inputs
/payroll/runs/{id}:calculate
/payroll/runs/{id}:validate
/payroll/runs/{id}:approve
/payroll/runs/{id}:post
/payroll/runs/{id}:create-payment-batch
/payroll/runs/{id}:reconcile
/hr-services
/hr-cases
/knowledge
/survey-campaigns
/employee-relations-cases
/safety/incidents
/safety/corrective-actions
/workspaces/hr
/workspaces/manager
/self/profile
/self/payslips
/self/leave
```

Transições são comandos explícitos; não existe `PATCH status`.

### 7.3 Permissões

Definir capacidades granulares:

```text
hr.people.read_basic / read_sensitive / manage
hr.planning.read / manage / approve
hr.recruiting.read / manage / decide
hr.candidate.self
hr.journeys.manage
hr.employment.read / manage
hr.compensation.read / manage
hr.benefits.read / manage
hr.skills.manage / hr.learning.manage
hr.performance.manage / calibrate
hr.talent.read / manage
hr.time.read / manage
hr.leave.request / approve
hr.payroll.prepare / validate / approve / post / pay / reconcile
hr.documents.read / manage
hr.service.manage
hr.engagement.manage
hr.relations.restricted
hr.safety.manage
hr.medical.restricted
hr.audit.read
hr.self.read
hr.team.read
```

RBAC combina ABAC por tenant, entidade legal, org unit, self/team, classificação,
purpose, workflow e maker-checker. Leituras de salário, BI, NUIT, banco ou
documento restrito geram access audit.

## 8. Eventos e integrações

### 8.1 Envelope

Adoptar CloudEvents 1.0 com `id`, `source`, `type`, `subject`, `time`,
`datacontenttype`, `dataschema` e extensões `tenantid`, `legalentityid`,
`aggregateid/version`, `correlationid`, `causationid`, `idempotencykey` e
`classification`. Payloads têm PII mínima e nunca incluem salário, banco ou
documento em eventos genéricos.

### 8.2 Outbox/inbox

- evento na transacção do aggregate;
- delivery independente por consumer;
- drain com `FOR UPDATE SKIP LOCKED`;
- retry exponencial, jitter e DLQ;
- inbox única por `(consumer, event_id)`;
- checkpoint, lag, rebuild e reconciliação;
- compatibility test de schema.

Um único `delivery_status` no evento não suporta vários consumidores.

### 8.3 TMS e Oficina

TMS publica viagem, tempo confirmado e HOS. Oficina publica mão-de-obra
confirmada/anulada e requisitos. HRM aplica elegibilidade, política e aprovação;
o facto cru nunca cria pagamento.

Na migração:

- `Employee.driver_id` vira `hr_worker_driver_links`;
- `TaskLaborLog` ganha `worker_assignment_id`;
- `user_id` permanece temporariamente como actor do registo;
- custo aplicado continua snapshot imutável;
- `WorkshopStaffRate` vira projecção de custo burdened sem salário;
- dados laborais de Driver tornam-se projections até remoção.

Trace Context W3C atravessa HTTP/outbox/consumers e a telemetria segue
OpenTelemetry. PII e IDs humanos não são labels.

## 9. Privacidade, segurança e auditoria

- cifragem de envelope em campos restritos;
- `key_version` para rotação e KMS/Key Vault como raiz;
- HMAC keyed normalizado para pesquisa/unicidade;
- nunca hash simples de NUIT/BI enumerável;
- chaves separadas por ambiente/finalidade;
- backups cifrados e restauração testada;
- audit genérico com campos redigidos/hashes, nunca snapshots salariais em claro;
- leitura do audit sensível também auditada.

Threat model HRM-00 cobre exfiltração cross-tenant, abuso de gestor,
auto-aprovação, retroactividade salarial, replay de ponto/pagamento, adulteração
de ruleset, malware, fuga por export/log/cache/analytics, insider, owner que
bypassa RLS, dispositivo offline comprometido e inferência em grupos pequenos.

Controlos serão ligados a requisitos versionados OWASP ASVS e NIST SSDF, com
owner, evidência e estado.

## 10. Frontend

Manager:

```text
/rh/organizacao
/rh/planeamento
/rh/recrutamento
/rh/onboarding
/rh/pessoas
/rh/vinculos
/rh/tempo
/rh/ferias
/rh/competencias
/rh/aprendizagem
/rh/desempenho
/rh/carreiras
/rh/sucessao
/rh/recompensas
/rh/beneficios
/rh/servicos
/rh/engagement
/rh/relacoes-laborais
/rh/saude-seguranca
/rh/payroll
/rh/analytics
/rh/compliance
```

Usar BFF; não persistir salário/PII em localStorage, IndexedDB ou cache do
browser. A UI mostra effective date, fonte, versão, freshness, histórico, diff,
estados falhados/stale e explicação de cálculo. Não converte erro em lista vazia.
Contratos gerados substituem o `hr-api.ts` genérico.

Existem quatro experiências distintas, não um único menu com permissões:

- Candidate Portal: candidatura, comunicação, entrevista, oferta e privacidade;
- Employee Center: perfil, knowledge, pedidos, jornada, aprendizagem, carreira,
  objectivos, benefícios, tempo e payslips;
- Manager Hub: equipa, posição, hiring, onboarding, tempo, desenvolvimento,
  performance, rewards proposals e casos permitidos;
- HR Workspace: strategy, operations, recruiting, talent, rewards, payroll,
  service delivery, ER/OHS, analytics, compliance e configuration.

Self-service expõe apenas os próprios dados. Offline limita-se a ponto e
rascunhos; não oferece salário persistente, regras ou operações de payroll.
WCAG 2.2 AA é gate.

## 11. Migração

```text
expand schema
 -> backfill idempotente
 -> validar/reconciliar
 -> shadow read/calculate
 -> trocar writer por aggregate
 -> canary por tenant
 -> contract após duas releases estáveis
```

| Legado | Destino/tratamento |
|---|---|
| `employees` | person + worker + employment + assignment |
| `base_salary` | compensation version `LEGACY_IMPORT` |
| `irps_tax_percentage` | evidência; nunca regra legal activa |
| `driver_id`, `user_id` | links temporais validados |
| documentos | scan, classificação e retenção |
| absences | leave request/ledger preservando origem |
| payroll slips | closed `UNVERIFIED_LEGACY`, sem recalcular |
| salary advances | deduction schedule reconciliado |
| Driver labour data | projection temporária |
| Workshop rates | workforce cost projection |

Ambiguidade gera `migration_exception`; não se inventam data, entidade, taxa,
vínculo ou aprovação. Usar feature flags por tenant, geração legada desactivada,
shadow sem posting, canary e piloto de um ciclo. Rollback é funcional por flag e
dados são corrigidos forward-only.

## 12. Testes e evidência

| Camada | Prova obrigatória |
|---|---|
| unit | value objects, policies, FSM, kernel |
| property | intervalos, rounding, invariantes financeiras |
| golden | casos assinados por RH/Contabilidade/Legal |
| repository | constraints, locks, composite FKs |
| RLS | role restrita e tenants adversariais |
| authorization | campos, self/team e maker-checker |
| contract | OpenAPI, eventos e typed failures |
| integration | TMS, Oficina, files, ledger, treasury |
| resilience | replay, out-of-order, DLQ, rebuild |
| migration | DB vazia, backfill repetido e comparação |
| E2E | personas e lifecycle completo |
| non-functional | carga, soak, pentest, WCAG e DR |

Adicionar Hypothesis para property tests. Invariantes críticas:

- versões efectivas não se sobrepõem;
- cross-tenant falha abaixo da API;
- mesmo snapshot produz mesmo hash;
- débito iguala crédito;
- pagamento não excede líquido aprovado;
- replay produz um efeito;
- evento atrasado não regride estado;
- closed adjustment referencia origem;
- utilizador sem permissão não infere salário;
- replay offline não duplica ponto.

Cada história entrega teste, RLS/auth evidence, contract diff, migration report,
métricas, alertas, runbook, sign-off funcional e decisão GO/NO-GO. O baseline
actual de lint e dois testes tipados não certifica payroll.

## 13. Operação e SLOs

Métricas: latência/erro, duração de payroll, divergência determinística, inputs
não reconciliados, outbox/inbox lag e DLQ, freshness de availability, acessos
negados, documentos em quarentena, ajustes e diferença payroll-ledger-bank.

| Serviço | Objectivo inicial |
|---|---|
| factor HR de disponibilidade | p95 < 300 ms |
| freshness operacional | p95 < 60 s |
| API comum | p95 < 500 ms |
| payroll | benchmark pelo volume piloto; job assíncrono |
| recuperação | RPO <= 15 min; RTO <= 4 h |

Os valores só viram compromisso após benchmark production-like. Criar runbooks
para divergência, ruleset incorrecto, lag/DLQ, malware, fuga salarial, posting,
batch parcial, reconciliação, dispositivo comprometido, cutover e DR.

## 14. Sequência de entrega

### A — HRM-00

ADRs: boundary/identity, temporalidade/money, privacidade/autorização,
eventos/outbox-inbox, motor payroll e migração/cutover. Completar threat model,
classificação, matriz legal, feature flags e evidence ledger. Gate H0.

### B — HRM-01/02, Core & Strategy

Organization, person/worker/employment/position, total workforce, workforce
planning, position control e headcount budget. Gate H1 com RLS real.

### C — HRM-03 a HRM-07, Attract, Join, Reward & Operate

Recruiting, candidate, offer, onboarding/journeys, compensation/benefits, tempo,
leave, availability, skills e learning. Gates H2/H3.

### D — HRM-08 a HRM-12, Talent, Experience & Relations

Goals/performance, career/mobility/succession, HR Service Delivery, engagement,
ER/OHS e contratos/eventos corporativos. Gate H4.

### E — HRM-13 a HRM-15, Payroll & Workspaces

Rulesets, kernel, golden corpus, posting ERP-09, payments ERP-10, reconciliação e
quatro workspaces por persona. Gate H5; payroll permanece shadow antes disso.

### F — HRM-16 a HRM-18, Insight & Certification

Human capital reporting, analytics, responsible AI, migração final, piloto
enterprise, soak, pentest, WCAG, DR e sign-offs. Gates H6/H7 e ERP E5.

### 14.1 PR slices

1. capabilities/flags;
2. org/composite FKs;
3. person/worker/RLS;
4. employment/temporal constraints;
5. position/link projections;
6. workforce plan/position budget;
7. requisition/candidate/application;
8. offer/pre-hire/journey;
9. compensation/benefits;
10. skills/learning;
11. calendar/time/leave/availability;
12. goals/review/calibration;
13. career/mobility/succession;
14. service delivery/knowledge;
15. engagement/ER/OHS vaults;
16. outbox/inbox/adapters;
17. payroll DSL/kernel/golden;
18. run/posting/payment;
19. four workspaces/analytics;
20. backfill/shadow/canary/pilot.

Um PR não combina migração destrutiva, algoritmo legal e cutover.

## 15. Matriz de rastreabilidade

| ID | Entrega física | Dependências vinculativas | Owner principal | Evidência de saída |
|---|---|---|---|---|
| HRM-00 | ADR-009..014, threat model, classificação, matriz legal, flags | G0-G3, ERP-00 | TL + SEC + PO | decisões assinadas e ledger de riscos |
| HRM-01 | org, person, worker, employment, job, position e links | HRM-00, ERP-03/04 | BE + FE-M + PO | constraints temporais, RLS e lifecycle E2E |
| HRM-02 | workforce planning e position control | HRM-01 | RH + Finanças + BE | plan/budget/actual reconciliados |
| HRM-03 | recruiting, candidate e offer | HRM-01/02 | Talent + FE-M + BE | requisition-to-offer E2E |
| HRM-04 | journeys e lifecycle | HRM-01/03 | HR Ops + IT + BE | pre-hire/onboarding/offboarding E2E |
| HRM-05 | compensation, benefits e rewards | HRM-01/02 | Rewards + Finanças | budgets/eligibility/approvals |
| HRM-06 | time, leave e availability | HRM-01 | HR Ops + QA | offline, ledger e decisão explicável |
| HRM-07 | skills, learning e certifications | HRM-01/04 | L&D + QA | curriculum/compliance E2E |
| HRM-08 | goals, performance e calibration | HRM-01/07 | Talent + RH | review/appeal/bias evidence |
| HRM-09 | career, mobility e succession | HRM-02/07/08 | Talent + RH | critical-role coverage |
| HRM-10 | HR service delivery e knowledge | HRM-01/04 | HR Ops + FE-M | case SLA/privacy |
| HRM-11 | engagement, ER e OHS | HRM-01/10 | RH + Legal + OHS | anonymity/investigation/safety |
| HRM-12 | events e adapters corporativos | HRM-01, WKS-04 | TL + BE + QA | replay/DLQ/reconciliation |
| HRM-13 | payroll rules/kernel/runs | HRM-05/06/12 | Payroll + Legal + BE | golden/hash/reproduction |
| HRM-14 | posting/payment/statutory | HRM-13, ERP-09/10 | Finanças + BE | payroll-ledger-bank |
| HRM-15 | candidate/employee/manager/HR workspaces | HRM-03..14 | FE-M + UX + SEC | persona E2E/WCAG |
| HRM-16 | reporting e workforce analytics | HRM-02..12, BI-01/02 | RH + BI | ISO metrics/rebuild/drill-down |
| HRM-17 | responsible HR Intelligence | HRM-16, BI-06/08 | TL + SEC + Legal | fairness/appeal/kill switch |
| HRM-18 | migration/pilot/DR/certification | HRM-00..17 | Todos | lifecycle enterprise e sign-offs |

### 15.1 Caminho crítico

```text
G0-G3
  -> HRM-00
     -> ERP-03/04
        -> HRM-01 -> HRM-02
           -> HRM-03..07
              -> HRM-08..12
                 -> HRM-13
                    -> ERP-09/10 + HRM-14
                       -> HRM-15/16
                          -> HRM-17
                             -> HRM-18 / ERP E5
```

ERP-03/04, WKS-04 e ERP-09/10 não impedem preparar contratos, kernels e testes,
mas impedem a promoção dos respectivos gates. Nenhuma equipa deve contornar uma
dependência com tabelas duplicadas dentro de HRM.

### 15.2 Evidence ledger por entrega

Cada ID mantém um registo com:

- commit e migration revision;
- OpenAPI/event schema version;
- dataset e ambiente de teste;
- comando exacto e resultado;
- reconciliation hash/report;
- vulnerabilidades e excepções abertas;
- owner, reviewer independente e timestamp;
- fonte e vigência legal quando aplicável;
- decisão GO/NO-GO e condições.

Evidência local, ambiente production-like e produção são estados diferentes. Um
gate não herda automaticamente evidência de outro ambiente.

## 16. Gates

| Gate | GO | NO-GO automático |
|---|---|---|
| H0 | ADRs, threat model, dados, legal matrix e owners | regra sem fonte/validade |
| H1 | core, total workforce, plan e position control provados | pessoa/salário fundidos ou headcount sem budget |
| H2 | recruit-to-onboard e rewards/benefits controlados | decisão automática ou offer sem approval |
| H3 | time/leave/learning/availability reconciliam | replay duplica ou facto cru paga |
| H4 | talent, service, engagement, ER e OHS seguros | caso/medical data exposto ou decisão sem appeal |
| H5 | payroll, posting, payment e quatro workspaces verdes | diário pré-aprovação ou field leak |
| H6 | human capital metrics e AI explicáveis/auditáveis | KPI sem lineage ou decisão adversa autónoma |
| H7 | lifecycle enterprise, pilot, soak, WCAG, DR e sign-offs | diferença financeira, legal ou privacy aberta |

Estado actual:

```text
Arquitectura: definida para planeamento
Novo boundary SOTA: não implementado
Payroll real: NO-GO
Certificação legal/operacional: inexistente
```

## 17. Definition of Done

Uma capacidade só está DONE quando contrato, schema e invariantes estão
versionados; RLS/ABAC e segregação foram provados; PII não vaza; migrations
funcionam numa DB vazia e histórica; backfill reconcilia; testes aplicáveis estão
verdes; métricas, alertas e runbook existem; OpenAPI coincide com runtime;
evidência production-like está no ledger; e os owners funcional, legal e
contabilístico assinam o que lhes compete.

Código presente, UI demonstrável ou testes mockados não equivalem a certificação.

## 18. Normas técnicas de referência

- CloudEvents 1.0 para envelope e compatibilidade de eventos:
  `https://github.com/cloudevents/spec`;
- PostgreSQL 16 range types e exclusion constraints:
  `https://www.postgresql.org/docs/16/rangetypes.html`;
- PostgreSQL 16 row-level security:
  `https://www.postgresql.org/docs/16/ddl-rowsecurity.html`;
- RFC 8785 para canonicalização JSON dos snapshots:
  `https://www.rfc-editor.org/rfc/rfc8785.html`;
- W3C Trace Context:
  `https://www.w3.org/TR/trace-context/`;
- OpenTelemetry Semantic Conventions:
  `https://opentelemetry.io/docs/specs/semconv/`;
- OWASP ASVS 5.0.0 para requisitos verificáveis de segurança:
  `https://owasp.org/www-project-application-security-verification-standard/`;
- NIST SP 800-218 SSDF para práticas de desenvolvimento seguro:
  `https://csrc.nist.gov/pubs/sp/800/218/final`.
- ISO 30414:2025 para reporting de capital humano:
  `https://www.iso.org/standard/30414`;
- ISO 30405:2023 para recrutamento:
  `https://www.iso.org/standard/79488.html`;
- ISO 30409:2016 para workforce planning:
  `https://www.iso.org/standard/64150.html`;
- ISO 30415:2021 para diversidade e inclusão:
  `https://www.iso.org/standard/71164.html`;
- ISO 45001:2018 para gestão de saúde e segurança ocupacional:
  `https://www.iso.org/standard/63787.html`.

Estas normas orientam contratos e evidência técnica; não substituem validação
laboral, fiscal, contabilística ou de protecção de dados em Moçambique.
