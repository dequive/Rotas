# PRD — HRM ROTAS: Gestão Moderna de Pessoas

Versão: 2.0

Data: 2026-07-29

Estado: visão enterprise proposta; requer validação do operating model de RH,
não implementada nem certificada

Owner de produto: Produto + RH/Finanças

Owner técnico: Tech Lead + Backend

Âmbito: sistema corporativo de gestão de pessoas de cada tenant, transversal a
todas as funções, entidades legais e unidades de negócio

Blueprint técnico: `docs/HRM_IMPLEMENTATION_BLUEPRINT.md`

## 1. Decisão de produto

O HRM do ROTAS será a plataforma tenant-scoped de Human Capital Management de
cada empresa cliente. É dirigido pelo Gestor de RH e serve toda a organização:
administração, finanças, comercial, procurement, armazém, segurança, tecnologia,
operações, TMS, Oficina, liderança, trabalhadores permanentes e contingentes.

TMS e Oficina são consumidores e produtores de factos operacionais, não o centro
do modelo de pessoas. Motorista, mecânico e recepcionista são apenas exemplos de
job profiles numa arquitectura de funções extensível.

O HRM nasce dentro do monólito modular FastAPI definido pelo ADR-001. A fronteira
de domínio, os contratos e a ownership dos dados devem permitir extracção futura,
mas não se introduz um microserviço antes de existir necessidade operacional
demonstrada.

O módulo respeita a hierarquia vinculativa do ROTAS:

```text
Operador ROTAS SaaS
  -> tenant independente
     -> entidade legal empregadora
        -> filial/local de trabalho
           -> unidade de negócio
              -> departamento
                 -> equipa
                    -> posição
                       -> vínculo/atribuição da pessoa
     -> clientes próprios do tenant
```

Um colaborador de um tenant nunca é uma identidade operacional global da
plataforma. A mesma pessoa pode ter contas ou vínculos em organizações diferentes,
mas qualquer associação entre tenants é proibida por defeito e não é inferida por
NUIT, BI, telefone, email ou biometria.

### 1.1 Operating model de RH

O produto deve suportar quatro níveis complementares:

```text
People Strategy
  -> organização, workforce planning, headcount, skills e sucessão
Talent Lifecycle
  -> atrair, seleccionar, admitir, desenvolver, reconhecer, mobilizar e reter
People Operations
  -> vínculo, documentos, tempo, benefícios, remuneração, payroll e saída
Employee Experience & Governance
  -> self-service, manager service, casos, relações laborais, segurança,
     engagement, analytics, privacidade e compliance
```

O Gestor de RH tem um workspace próprio para governar políticas, estrutura,
capacidade, talento, risco, serviço e compliance. Não é apenas um utilizador que
aprova férias ou executa payroll.

### 1.2 População abrangida

O modelo cobre, sem os fundir:

- candidato e ex-candidato;
- pre-hire;
- empregado permanente ou a prazo;
- trabalhador por turno, horário ou produção;
- gestor e executivo;
- estagiário, aprendiz e trainee;
- consultor, contractor, temporário e trabalhador de agência;
- ex-colaborador elegível para documentos ou obrigações posteriores;
- dependente/beneficiário apenas quando necessário a benefícios;
- utilizador sem vínculo e worker sem conta de utilizador.

### 1.3 Personas de produto

- Director/Gestor de RH e HR Business Partner;
- HR Operations e HR Service Desk;
- recruiter e hiring manager;
- especialista de onboarding;
- compensation & benefits;
- payroll specialist;
- learning & development;
- performance/talent/succession;
- workforce planner;
- employee relations, Legal e Compliance;
- saúde, segurança e medicina ocupacional, em vault segregado;
- line manager e manager-of-managers;
- colaborador, candidato e trabalhador contingente;
- Finanças, Tesouraria, IT/IAM, Segurança, auditor e representante laboral.

## 2. Resultado pretendido

O HRM deve permitir que cada tenant:

1. planeie estrutura, posições, headcount, skills, custo e cenários;
2. recrute com requisição aprovada, experiência do candidato, avaliação
   estruturada, oferta, pre-hire e onboarding;
3. mantenha uma fonte temporal de toda a relação pessoa-empresa;
4. administre trabalhadores permanentes e contingentes;
5. governe remuneração total, benefícios, elegibilidade e payroll;
6. execute tempo, escalas, férias e capacidade para qualquer função;
7. alinhe objectivos, feedback, performance e reconhecimento sem ranking cego;
8. desenvolva competências por aprendizagem, carreira e mobilidade interna;
9. identifique posições críticas, talento, readiness e planos de sucessão;
10. entregue serviços de RH por catálogo, knowledge base, casos e SLAs;
11. trate engagement, relações laborais, reclamações, disciplina, saúde,
    segurança, bem-estar e accommodations com confidencialidade adequada;
12. ofereça experiências próprias a candidato, colaborador, gestor e RH;
13. produza reporting de capital humano auditável e workforce analytics;
14. integre TMS, Oficina, ERP, IAM e terceiros sem duplicar ownership;
15. prove isolamento, privacidade, fairness, continuidade e legalidade antes de
    qualquer promoção real.

## 3. Verdade actual no repositório

Existe um scaffold funcional em `backend/app/modules/hr` com:

- `employees`, documentos, ausências, recibos/linhas de payroll, códigos de
  payroll e adiantamentos;
- endpoints de cadastro, documentos, geração/listagem de payroll, adiantamentos
  e exportação;
- permissões iniciais `hr.read`, `hr.write`, `hr.salary.view`,
  `hr.payroll.generate` e `hr.payroll.approve`;
- RLS/tenant filtering inicial e integração contabilística parcial.

Esse estado não equivale ao HRM definido neste PRD e não está certificado para
processar remuneração real. Lacunas críticas confirmadas:

- `Employee` mistura pessoa, função, departamento, vínculo, remuneração e
  fiscalidade;
- salário-base e percentagem de IRPS são campos mutáveis do colaborador, sem
  vigência, pacote de compensação ou snapshot legal;
- não existem estrutura organizacional, posição, atribuição, competências,
  certificações, ponto, turnos, férias ou motor de disponibilidade completos;
- não existem workforce planning, recruiting/ATS, onboarding journeys,
  learning, performance, career, succession, benefits, HR case management,
  engagement, employee relations ou OHS como capacidades empresariais;
- o cálculo actual usa mês de 30 dias, multiplicadores/valores fixos e percentagem
  directa de IRPS;
- o lançamento contabilístico é criado durante a geração de uma folha ainda em
  `draft`, antes de uma máquina de estados de validação e aprovação;
- não existe catálogo versionado de regras legais, memória de cálculo completa,
  maker-checker do run, fluxo de pagamento/fecho nem ajustes retroactivos;
- não foram encontrados testes dedicados ao domínio HR/payroll na baseline
  inspeccionada.

Consequência: o código actual é legado a migrar por expand/contract. Não pode ser
promovido por simples extensão de tabelas ou por uma alteração grande e
destrutiva da migration existente.

## 4. Princípios vinculativos

### 4.1 Fontes de verdade

- HRM é owner de pessoa tenant-scoped, vínculo laboral, posição, remuneração,
  tempo aprovado, férias, competências, certificações e payroll.
- TMS é owner de viagem, distância, incidentes e execução do motorista.
- Oficina é owner de OS, tarefa, tempo de mão de obra, QC, garantia e retrabalho.
- Contabilidade é owner do diário finalizado; Tesouraria é owner do pagamento e
  reconciliação bancária.
- BI/HR Intelligence é leitura derivada. Nunca altera tabelas transaccionais.
- Um dado operacional só se torna input pagável depois de passar pela política
  de elegibilidade, reconciliação e aprovação aplicável.

### 4.2 Integração sem escrita cruzada

“HRM não escreve nos módulos operacionais” significa que não executa SQL nem
altera tabelas de TMS/Oficina. Não significa silêncio entre domínios:

- HRM publica eventos como `EmploymentTerminated`, `LeaveApproved`,
  `CertificationExpired` e `AvailabilityChanged`;
- HRM expõe uma API tenant-scoped de elegibilidade/disponibilidade, com motivos;
- TMS e Oficina publicam factos operacionais pelo outbox;
- qualquer acção resultante de recomendação regressa como comando explícito à
  API do domínio owner, sujeito a RBAC, validação, idempotência e auditoria.

### 4.3 Correcção temporal

Todo facto relevante deve distinguir:

- `effective_from` / `effective_to`: quando vale no negócio;
- `occurred_at`: quando aconteceu;
- `recorded_at`: quando o sistema o registou;
- `approved_at`: quando se tornou aprovado, se aplicável;
- `supersedes_id` ou evento de reversão: o que corrige.

Alterações retroactivas nunca reescrevem um run de payroll fechado. Produzem
diferença explicável num run suplementar ou no período seguinte, conforme a
política legal aprovada.

### 4.4 Fail-closed

O sistema bloqueia e explica, em vez de assumir:

- identidade, vínculo ou entidade legal ambíguos;
- política legal ausente, expirada ou não aprovada;
- moeda, calendário, centro de custo ou conta contabilística em falta;
- evento operacional duplicado, inválido, fora de ordem ou não reconciliado;
- conflito de escala, descanso, férias, suspensão ou certificação;
- cálculo não balanceado, run não aprovado ou período contabilístico fechado;
- tentativa de um actor preparar, aprovar, pagar e reconciliar a mesma folha
  quando a segregação exigir actores diferentes.

## 5. Bounded contexts

### 5.1 People Identity & Organization

Responsável por:

- `Person`: identidade civil e contactos;
- `WorkerProfile`: identidade de trabalho tenant-scoped e número interno;
- `LegalEntityEmployer`, `WorkLocation`, `BusinessUnit`, `Department`, `Team`;
- árvore organizacional versionada;
- `JobFamily`, `JobProfile`, `Position` e `PositionAssignment`;
- linha de reporte e centro de custo efectivos no tempo;
- ligação controlada a `User`, `Driver` e recursos de Oficina.

`Person`, `User`, `Driver` e `Employee/Employment` são agregados distintos:

- pessoa não implica login;
- login não implica vínculo activo;
- motorista é um perfil/recurso operacional, não a pessoa completa;
- desligar o vínculo revoga acessos e elegibilidade sem apagar viagens, OS ou
  recibos históricos.

### 5.2 Workforce Administration

Responsável por:

- admissão mínima e checklist;
- `EmploymentRelationship` e versões contratuais;
- tipo de vínculo, categoria profissional, período experimental, carga horária,
  local, empregador e motivo de alteração;
- documentos, verificações, validade, confidencialidade e retenção;
- `CompensationPackageVersion` e componentes;
- promoções, transferências, suspensão, aviso e desligamento;
- checklist de offboarding, revogação de acesso, devolução de activos e
  obrigações pendentes.

Contrato não contém salário mutável. O pacote de compensação possui versões:

```text
CompensationPackageVersion
  -> BaseSalary
  -> FixedAllowance
  -> VariableAllowance
  -> OvertimePolicy
  -> CommissionPlan
  -> Bonus
  -> Reimbursement
  -> DeductionAuthorization
```

Cada componente declara vigência, moeda, periodicidade, base de incidência de
IRPS/INSS, tratamento contabilístico, centro de custo e regra de arredondamento.

### 5.3 Time, Leave & Availability

Responsável por:

- calendários da entidade legal e do local;
- feriados, jornadas, turnos, escalas e períodos de descanso;
- eventos de entrada/saída/pausa, origem e confiança;
- correcções append-only com pedido, motivo, aprovação e diferença;
- horas normais, nocturnas, extra, descanso e faltas;
- políticas e contas de férias/ausências;
- pedido, aprovação, cancelamento, gozo e retorno;
- projecção de capacidade e disponibilidade.

Disponibilidade não é um campo livre nem substitui a escala. É uma decisão
derivada e explicável que pode conter múltiplos motivos:

```text
AVAILABLE | PLANNED | ON_SHIFT | ON_TRIP | ON_WORK_ORDER
LEAVE | SICK | TRAINING | REST | SUSPENDED
NON_COMPLIANT | EMPLOYMENT_INACTIVE | UNKNOWN
```

A resposta canónica é:

```json
{
  "eligible": false,
  "as_of": "2026-07-26T10:00:00+02:00",
  "person_id": "uuid",
  "assignment_id": "uuid",
  "reasons": [
    {
      "code": "CERTIFICATION_EXPIRED",
      "source": "hrm",
      "effective_until": null,
      "override_allowed": false
    }
  ],
  "decision_version": 7
}
```

TMS e Oficina continuam owners da atribuição a viagem/OS. Antes de atribuir,
consultam a decisão; ao confirmar a atribuição, publicam o facto operacional que
actualiza a projecção.

### 5.4 Skills, Competency & Certification

Responsável por:

- catálogo de competência, especialidade e nível;
- evidência de avaliação;
- certificação, emissor, documento, validade e renovação;
- requisitos de `JobProfile`, posição, tipo de viatura, carga ou tarefa;
- matriz de gaps e elegibilidade;
- recomendações de formação derivadas, nunca punições automáticas.

Competência e certificação são distintas. Uma pessoa pode demonstrar competência
sem possuir a certificação legal exigida, mas isso não remove o bloqueio
regulatório da operação.

### 5.5 Payroll & Statutory Compliance

Responsável por:

- calendário e período de payroll por entidade legal;
- catálogo de rubricas;
- `RuleSetVersion` e regras efectivas;
- recolha, freeze, reconciliação e aprovação de inputs;
- cálculo determinístico, memória de cálculo e hash;
- folha, recibo, run suplementar e ajuste;
- obrigações de empregado e empregador;
- aprovação, contabilização, pagamento e fecho;
- outputs legais e submissões com recibo/evidência;
- reconciliação payroll-to-ledger-to-bank.

Cada regra é declarativa e versionada:

```text
input -> eligibility -> taxable/contributory base
      -> formula/table -> rounding -> result
      -> explanation -> accounting mapping
```

Uma regra aprovada não é editada. Uma mudança cria versão com vigência futura,
autor, aprovador, fonte legal, testes e checksum.

### 5.6 Performance & Productivity

Responsável por projections/read models de:

- tempo padrão versus real;
- produtividade e utilização;
- retrabalho, garantia, QC e incidentes;
- assiduidade e evolução;
- custo de mão de obra previsto versus realizado;
- métricas configuráveis por perfil, equipa, local e período.

O contexto deve acompanhar a métrica: complexidade da tarefa, turno, equipamento,
disponibilidade de peças, tempo de espera, composição da equipa e qualidade do
dado. Um ranking sem contexto não pode fundamentar decisão disciplinar.

### 5.7 HR Intelligence

Camada read-derived para:

- risco de sobrecarga e fadiga;
- gaps de competências/certificações;
- risco de ausência, rotatividade e sucessão;
- recomendação de formação;
- simulação de capacidade e custo de pessoal.

Regras vinculativas:

- começar por regras determinísticas e explicáveis;
- separar `fact`, `forecast`, `recommendation`, `simulation`, `decision` e
  `command_result`;
- não inferir saúde, filiação sindical, gravidez, religião, etnia ou outras
  características sensíveis para decidir emprego, salário ou disciplina;
- nenhuma recomendação encerra contrato, reduz salário, aplica sanção ou altera
  escala sem decisão humana autorizada e direito de contestação;
- modelos possuem dataset lineage, versão, finalidade, owner, métricas de erro,
  bias/fairness, drift, fallback e kill switch;
- benchmarking cross-tenant exige base legal/consentimento, anonimização,
  agregação, coorte mínima e testes contra inferência.

### 5.8 Audit, Privacy & Compliance

Responsável por:

- timeline laboral reconstruível;
- auditoria de mutação e de leitura de dados altamente sensíveis;
- acesso break-glass temporário e justificado;
- retenção, legal hold, exportação e eliminação conforme política;
- registo de consentimento quando ele for a base aplicável;
- casos de correcção, reclamação e contestação;
- ledger de evidências legais e operacionais.

### 5.9 Workforce Strategy & Position Control

Responsável por:

- planos de workforce por entidade, unidade, local, job family e skill;
- posição autorizada, budget, FTE, vacancy e período;
- cenários `baseline`, `grow`, `freeze`, `redeploy`, `outsource`;
- procura versus capacidade, custo e time-to-productivity;
- workflow de aprovação de headcount e ligação à requisição;
- comparação plano, forecast e realizado sem alterar o organograma oficial.

Uma posição não pode ser recrutada ou ocupada acima do FTE/budget aprovado sem
override explícito. Cenários são imutáveis e nunca se tornam plano por acidente.

### 5.10 Talent Acquisition & Candidate Experience

Responsável por:

- job requisition ligada a posição, budget, skills e hiring team;
- publicação interna/externa, fontes e talent pools;
- candidato, consentimento, retenção e preferências de contacto;
- candidatura, screening, entrevista, scorecard e assessment;
- conflito de interesse, feedback estruturado e decisão;
- offer versionada, aprovação, aceite/recusa e conversão para pre-hire;
- candidate portal, comunicação, SLA e pedido de eliminação/correcção.

O candidato não é `Person/Worker` antes da conversão autorizada. Currículos e
notas de entrevista têm acesso e retenção próprios. IA pode apoiar matching ou
resumo, mas não rejeita autonomamente nem usa atributos protegidos.

### 5.11 Onboarding, Journeys & Transitions

Responsável por journeys configuráveis de preboarding, onboarding, período
experimental, transferência, promoção, licença prolongada, retorno e saída:

- templates por entidade, função, local e tipo de vínculo;
- tarefas HR, manager, worker, IT, Facilities, Segurança e Payroll;
- dependências, SLA, evidência e escalonamento;
- documentos, assinatura e confirmação de políticas;
- conta, equipamento, acesso, formação e buddy;
- readiness do primeiro dia e time-to-productivity.

Journey orquestra módulos; não copia o inventário de activos nem as contas IAM.

### 5.12 Learning, Development & Skills

Responsável por:

- catálogo, curso, versão, sessão, capacidade e instrutor;
- currículos obrigatórios por posição/risco;
- inscrição, aprovação, presença, conclusão, avaliação e validade;
- plano de desenvolvimento individual;
- aprendizagem externa, custo, reembolso e evidência;
- skills profile com proveniência e nível de confiança;
- compliance learning e recertificação;
- mentoring/coaching e oportunidades internas.

Recomendação não equivale a skill verificada. Formação obrigatória vencida pode
bloquear elegibilidade apenas quando uma política aprovada o determinar.

### 5.13 Goals, Performance & Recognition

Responsável por:

- ciclos, templates e população;
- objectivos alinhados entre empresa, equipa e indivíduo;
- check-ins contínuos, feedback, one-to-one e reconhecimento;
- review self/manager/multi-rater configurável;
- calibration com acesso controlado e trilho de alterações;
- performance improvement plan com direito de resposta;
- ligação explícita, nunca automática, a compensation review;
- contestação, reavaliação e fecho.

Factos TMS/Oficina podem alimentar contexto, mas não são a avaliação. Qualidade
do dado, condições de trabalho e oportunidades devem acompanhar comparações.

### 5.14 Career, Mobility & Succession

Responsável por:

- career paths e requisitos de transição;
- aspirações e preferências privadas do trabalhador;
- gigs, project assignments e vagas internas;
- talent pools com critérios e validade;
- posições críticas e risco de cobertura;
- candidatos a sucessão, readiness e development actions;
- talent review e matriz configurável;
- mobilidade proposta, aprovada e effective-dated.

Ser identificado como sucessor não concede posição nem promessa. Acesso a
talent pools e succession é altamente restrito e toda leitura é auditada.

### 5.15 Total Rewards & Benefits

Responsável por:

- estruturas e ranges salariais por job/grade/local;
- compensation review cycles, budgets, propostas e approvals;
- mérito, promoção, bónus e incentivos;
- pay equity analysis com coortes protegidas;
- benefícios, planos, providers, elegibilidade e enrolment;
- dependentes/beneficiários com minimização de dados;
- total rewards statement;
- interface versionada com payroll e accounting.

Compensation planning é distinto do payroll: planeia e aprova a recompensa;
payroll executa valores effective-dated aprovados.

### 5.16 Employee Experience, Relations, Health & Safety

Inclui quatro subdomínios segregados:

1. **HR Service Delivery:** catálogo, pedidos, casos, knowledge articles, SLA,
   assignment groups, comentários e satisfação.
2. **Engagement:** surveys, pulse, lifecycle surveys, campanhas, planos de acção
   e anonimato por limiar de coorte.
3. **Employee Relations:** grievance, misconduct, allegation, involved parties,
   investigação, entrevista, evidência, corrective action, appeal, acomodação e
   relações colectivas.
4. **Occupational Health & Safety:** perigos, avaliações de risco, incidentes,
   near misses, lesões, acções correctivas, exames de aptidão e retorno ao
   trabalho.

Casos de relações laborais, denúncias e dados médicos não usam o ACL normal de
RH. Vivem em vaults lógicos separados, com equipas autorizadas, purpose,
need-to-know, legal hold e auditoria de leitura. O gestor vê apenas outcome
operacional necessário, nunca diagnóstico ou narrativa confidencial.

## 6. Modelo conceptual

| Agregado/entidade | Fonte de verdade | Regras mínimas |
| --- | --- | --- |
| `Person` | HRM | PII protegida; não é login nem vínculo |
| `WorkerProfile` | HRM | único por tenant/pessoa conforme política |
| `EmploymentRelationship` | HRM | pertence a entidade legal; effective-dated |
| `OrgNode` | HRM/ERP master data | árvore temporal sem ciclos |
| `JobProfile` | HRM | responsabilidades e requisitos |
| `Position` | HRM | headcount, equipa, local e centro de custo |
| `PositionAssignment` | HRM | histórico e regra de sobreposição |
| `CompensationPackageVersion` | HRM | imutável depois de aprovado |
| `CompensationComponent` | HRM | incidências e accounting mapping |
| `SkillEvidence` | HRM | nível, método, avaliador e validade |
| `Certification` | HRM | emissor, validade, verificação e documento |
| `Calendar` / `Shift` | HRM | timezone e vigência |
| `AttendanceEvent` | HRM | append-only, origem e confiança |
| `AttendanceCorrection` | HRM | maker-checker e diferença |
| `LeaveAccount` / `LeaveRequest` | HRM | saldo em ledger, não contador mutável |
| `AvailabilityProjection` | HRM read model | rebuild/reconcile e motivos |
| `OperationalFactInbox` | módulo produtor + HRM inbox | idempotência e provenance |
| `PayrollRuleSetVersion` | HRM | aprovado, versionado, testado |
| `PayrollRun` | HRM | FSM e segregação |
| `PayrollCalculation` | HRM | snapshot completo e hash |
| `PayrollLine` | HRM | rubrica, base, taxa/regra e explicação |
| `PayrollAdjustment` | HRM | referencia cálculo/período original |
| `PayrollPosting` | HRM + Accounting | idempotency key e reconciliação |
| `PayrollPaymentAllocation` | Treasury | valor, banco, estado e reconciliação |
| `StatutorySubmission` | HRM | tipo, versão, ficheiro, recibo e estado |
| `EmploymentTimelineEvent` | HRM | append-only |
| `HRProjection` | Analytics | read-derived e reconstruível |

Todas as tabelas tenant-scoped carregam `tenant_id`; relações sensíveis usam
foreign keys/uniques compostas com `tenant_id` para impedir referências
cross-tenant abaixo da API. Entidade legal, filial e scope organizacional são
adicionais ao tenant e nunca o substituem.

## 7. Máquinas de estados

### 7.1 Vínculo laboral

```text
PRE_ADMISSION
  -> ACTIVE
  -> ON_LEAVE
  -> ACTIVE
  -> SUSPENDED
  -> ACTIVE
  -> NOTICE
  -> TERMINATED
  -> ARCHIVED
```

- `TERMINATED` bloqueia nova operação efectiva depois da data de término.
- correcção da data de término é evento auditado e pode gerar ajuste de payroll;
- `ARCHIVED` não elimina histórico;
- recontratação cria novo vínculo, não ressuscita silenciosamente o anterior.

### 7.2 Pedido de ausência/férias

```text
DRAFT -> SUBMITTED -> MANAGER_APPROVED -> HR_APPROVED -> SCHEDULED -> TAKEN
                   \-> REJECTED
                                  \-> CANCELLED
```

O número de níveis é política do tenant/entidade legal. O pedido verifica saldo,
regras legais, conflitos de escala e demanda operacional, mas a demanda gera
alerta — não apaga um direito legal.

### 7.3 Ponto e correcção

```text
RECEIVED -> VALIDATED -> RECONCILED -> APPROVED -> LOCKED
             \-> EXCEPTION -> CORRECTION_REQUESTED -> APPROVED/REJECTED
```

O evento original permanece. A correcção regista antes/depois, motivo, anexos,
actor, aprovador e impacto em payroll.

### 7.4 Payroll run

```text
OPEN
  -> INPUTS_LOCKED
  -> CALCULATED
  -> VALIDATED
  -> APPROVED
  -> POSTED
  -> PAYMENT_PENDING
  -> PAID
  -> CLOSED
```

Saídas controladas:

- erro antes de aprovação: `FAILED` e nova tentativa idempotente;
- cancelamento antes de contabilização: `CANCELLED`, com motivo;
- depois de `POSTED`: reversão contabilística autorizada e run correctivo;
- depois de `CLOSED`: apenas `SUPPLEMENTAL`/`ADJUSTMENT`, nunca edição.

O diário contabilístico só nasce em `APPROVED -> POSTED`. Preparar, aprovar,
postar, pagar e reconciliar são capacidades separadas.

## 8. Contrato de eventos

O envelope canónico é obrigatório para TMS, Oficina, HRM e projections:

```json
{
  "spec_version": "rotas.events/1",
  "event_id": "uuid",
  "event_type": "workshop.labor.completed",
  "event_version": 1,
  "schema_version": "1.0.0",
  "producer": "rotas.workshop",
  "producer_version": "git-sha-or-release",
  "tenant_id": "uuid",
  "legal_entity_id": "uuid",
  "aggregate_type": "work_order_task",
  "aggregate_id": "uuid",
  "aggregate_version": 9,
  "subject_person_id": "uuid",
  "occurred_at": "2026-07-26T09:30:00+02:00",
  "recorded_at": "2026-07-26T09:30:02+02:00",
  "actor": {
    "kind": "user",
    "id": "uuid"
  },
  "correlation_id": "uuid",
  "causation_id": "uuid",
  "idempotency_key": "workshop:task:uuid:completed:v9",
  "data_classification": "confidential",
  "payload": {},
  "metadata": {}
}
```

Regras:

- outbox no produtor e inbox no consumidor;
- unicidade por `(tenant_id, producer, event_id)`;
- ordenação verificada por agregado, não por ordem global;
- `event_version` identifica a semântica; `schema_version`, a representação;
- evolução backward-compatible e consumer contract tests;
- assinatura/checksum quando o boundary o exigir;
- retry, dead-letter, observabilidade, replay e backfill autorizados;
- evento de correcção/reversão referencia o original;
- payload minimiza PII; não replica salário, documento ou dados bancários sem
  necessidade e autorização;
- todo projection suporta rebuild e reconciliação com a fonte transaccional.

Catálogo inicial de factos operacionais:

```text
tms.trip.assigned
tms.trip.started
tms.trip.completed
tms.trip.incident_recorded
tms.allowance_eligible
workshop.labor.started
workshop.labor.stopped
workshop.labor.completed
workshop.quality_control.failed
workshop.rework.opened
workshop.work_order.completed
```

Catálogo inicial de factos HR:

```text
hr.employment.activated
hr.employment.suspended
hr.employment.terminated
hr.position.assigned
hr.leave.approved
hr.shift.published
hr.certification.expired
hr.availability.changed
hr.payroll.run.closed
```

Um `trip.completed` ou `labor.completed` não gera comissão automaticamente. O
pipeline é:

```text
evento operacional
  -> inbox idempotente
  -> validação de schema/tenant/subject
  -> reconciliação com agregado origem
  -> mapping de política efectivo na data
  -> input de payroll
  -> aprovação/freeze
  -> cálculo
```

## 9. Payroll e localização Moçambique

### 9.1 Pacote legal versionado

O módulo usa `JurisdictionPack` por país/entidade legal e vigência. Para
Moçambique, o pacote cobre pelo menos:

- categorias de remuneração e bases de incidência;
- retenção de IRPS com situação pessoal/familiar aplicável;
- contribuição INSS de trabalhador e empregador;
- horas extraordinárias, trabalho nocturno, descanso e feriados;
- férias, ausências, licenças e indemnizações;
- arredondamentos, moeda e datas limite;
- Modelo 11, guia Modelo 19, comunicação/declaração anual aplicável, declaração
  INSS e recibo de vencimento;
- referências legais, fonte, data de consulta e responsável pela validação.

O código não assume que “Modelo 11/19” esgota as obrigações. A Autoridade
Tributária descreve o Modelo 11 como input da situação pessoal/familiar para a
retenção, o Modelo 19 como guia de pagamento e obrigações anuais adicionais.
Cada output exacto deve ser confirmado por contabilista/jurista moçambicano
antes do piloto.

### 9.2 Evidência e aprovação

Cada versão legal requer:

- fonte oficial anexada;
- interpretação documentada;
- autor e aprovador diferentes;
- data de vigência e de publicação;
- casos dourados calculados e assinados por especialista;
- comparação com cálculo independente;
- rollout, rollback e tenant opt-in quando aplicável;
- alerta e bloqueio quando não existe regra válida para o período.

### 9.3 Memória de cálculo

Cada recibo conserva:

- snapshot de pessoa/vínculo/posição/compensação relevante;
- versão de cada regra;
- inputs e suas fontes/eventos;
- bases tributáveis/contributivas;
- fórmula, taxa/tabela, arredondamento e resultado por linha;
- overrides, justificações e aprovações;
- hash do cálculo;
- links para diário, pagamento, submissão e ajuste.

O cálculo deve ser reproduzível anos depois sem depender da regra actualmente
activa.

### 9.4 Fontes oficiais verificadas em 2026-07-26

- Lei do Trabalho n.º 13/2023 listada pelo INSS:
  `https://www.inss.gov.mz/sdm_categories/leis/`
- Regulamento da Segurança Social revisto pelo Decreto n.º 56/2024:
  `https://www.inss.gov.mz/wp-content/uploads/2025/02/Decreto-56.2024-Altera-os-artigos-5-27-60-73-e-110-do-RSSO-aprovado-pelo-Decreto-5.2017-de-9-de-Outubro.pdf`
- INSS: taxa global de 7%, repartida em 4% empregador e 3% trabalhador:
  `https://www.inss.gov.mz/direitos-e-obrigacoes-do-contribuinte/`
- Autoridade Tributária: FAQ de IRPS, Modelo 11, retenção e obrigações anuais:
  `https://www.at.gov.mz/por/Perguntas-Frequentes2/IRPS`
- Autoridade Tributária: Guia de Pagamento IRPS — Modelo 19:
  `https://edeclaracao.at.gov.mz/formularios/irps/view/formulario_irps.aspx`
- Lei n.º 3/2017 é formalmente a Lei de Transacções Electrónicas:
  `https://www.inm.gov.mz/pt-br/content/br-n%C2%BA-5-de-090117-boletim-da-rep%C3%BAblica-i-serie`
- INTIC: artigos 63–65 da Lei n.º 3/2017 tratam obrigações de processadores e
  protecção de dados pessoais:
  `https://intic.gov.mz/questionario-de-fiscalizacao-das-tic/`

Estas referências são baseline de produto, não parecer jurídico. Como o INSS
abriu em 2026 uma consulta sobre revisão do regulamento, a vigência deve ser
reconfirmada no momento de cada release.

## 10. Segurança, privacidade e autorização

### 10.1 Modelo de acesso

RBAC por capacidade é combinado com ABAC por:

- tenant;
- entidade legal;
- unidade/filial/equipa;
- relação gestor-subordinado;
- finalidade;
- classificação do campo;
- estado do workflow;
- prazo de acesso.

Matriz mínima:

| Actor | Pode | Não pode por defeito |
| --- | --- | --- |
| Colaborador | ver/corrigir próprios dados, ponto, férias e recibos | ver outra pessoa |
| Gestor de linha | escala, disponibilidade e métricas da sua equipa | salário, banco, documento civil completo |
| RH | vínculo, documentos, férias e lifecycle | pagar/reconciliar sozinho |
| Preparador payroll | inputs, simulação e cálculo | aprovar o próprio run |
| Aprovador payroll | validar/aprovar | alterar silenciosamente inputs |
| Tesouraria | executar pagamento aprovado | alterar cálculo |
| Contabilidade | postar/reconciliar | alterar recibo |
| Auditor | leitura autorizada e evidência | mutar factos |
| Suporte ROTAS | acesso temporário break-glass aprovado | acesso operacional implícito |

`hr.read` genérico não pode devolver salário, conta bancária, documento,
informação médica ou incidente disciplinar. Endpoints e schemas devem aplicar
field-level authorization.

### 10.2 Controlos mínimos

- RLS/FORCE RLS com role operacional `NOBYPASSRLS`;
- foreign keys compostas tenant-scoped;
- encriptação em trânsito e em repouso;
- encriptação de campos de alto risco e gestão de chaves;
- storage com prefixo/política por tenant e URL de curta duração;
- auditoria de leitura/exportação de PII e payroll;
- mascaramento em logs, tracing, suporte e ambientes não produtivos;
- retenção por categoria, jurisdição e legal hold;
- export/delete/offboarding do tenant sem quebrar obrigações legais;
- sessões reforçadas/MFA para payroll, export e break-glass;
- rate limit, anti-enumeração e 404 estrito cross-tenant;
- threat model para insider, fraude de ponto, alteração de regra, folha fantasma,
  exfiltração, replay e pagamento duplicado.

### 10.3 Ponto offline e geolocalização

Offline-first requer:

- dispositivo registado e revogável;
- armazenamento local cifrado;
- `captured_at`, `received_at`, timezone, sequência local e nonce;
- assinatura/attestation proporcional ao risco;
- idempotência e detecção de relógio anómalo/replay;
- estado de confiança e fila de excepção;
- sincronização que nunca apaga o evento original.

Geolocalização é opt-in por política, finalidade e base legal. Guardar apenas a
precisão e tempo necessários; geofence falhada gera excepção, não acusação
automática.

## 11. Requisitos funcionais

### 11.1 Organização e pessoas

- HR-ORG-01: gerir entidades legais empregadoras, filiais, locais, unidades,
  departamentos, equipas e centros de custo com histórico.
- HR-ORG-02: rejeitar ciclos, órfãos e referências cross-tenant.
- HR-ORG-03: criar pessoa, worker profile e vínculo sem os fundir.
- HR-ORG-04: manter job families, job profiles, posições e headcount.
- HR-ORG-05: permitir múltiplas atribuições effective-dated conforme política.
- HR-ORG-06: ligar `User`, `Driver` e técnico de Oficina por referência explícita.

### 11.2 Administração laboral

- HR-WFA-01: admissão com checklist, documentos e approvals.
- HR-WFA-02: versões contratuais e de compensação imutáveis depois de aprovadas.
- HR-WFA-03: promoção, transferência, suspensão e término com data efectiva.
- HR-WFA-04: timeline laboral reconstruível.
- HR-WFA-05: offboarding revoga acesso e disponibilidade e reconcilia activos.
- HR-WFA-06: alertas de documento/certificação com owner e SLA.

### 11.3 Tempo, férias e disponibilidade

- HR-TIM-01: calendários, turnos e escalas effective-dated.
- HR-TIM-02: check-in/out/pausa online e offline.
- HR-TIM-03: correcção append-only com maker-checker.
- HR-TIM-04: cálculo explicável de horas e excepções.
- HR-TIM-05: saldo de férias como ledger reconciliável.
- HR-TIM-06: workflow de ausência e conflito com demanda.
- HR-TIM-07: API de disponibilidade com motivos e versão.
- HR-TIM-08: reconciliação ponto versus factos TMS/Oficina.

### 11.4 Competências

- HR-SKL-01: catálogo de skills, níveis e evidência.
- HR-SKL-02: certificação separada, verificada e com validade.
- HR-SKL-03: requisitos por job profile, tarefa, veículo e carga.
- HR-SKL-04: decisão fail-closed para certificação obrigatória expirada.
- HR-SKL-05: gap/recomendação de formação explicável.

### 11.5 Payroll

- HR-PAY-01: rule engine versionado por jurisdição e vigência.
- HR-PAY-02: rubricas e compensation mapping configuráveis.
- HR-PAY-03: freeze e reconciliação dos inputs.
- HR-PAY-04: simular antes de criar run oficial.
- HR-PAY-05: calcular com memória e hash reproduzíveis.
- HR-PAY-06: validar totais, anomalias e diferenças face ao período anterior.
- HR-PAY-07: maker-checker e FSM completo.
- HR-PAY-08: contabilizar apenas run aprovado, com idempotência.
- HR-PAY-09: pagamento e reconciliação bancária sem duplicação.
- HR-PAY-10: ajuste/suplementar sem editar período fechado.
- HR-PAY-11: recibo PDF acessível e verificável.
- HR-PAY-12: outputs fiscais/INSS versionados e submissão com recibo.

### 11.6 Desempenho e intelligence

- HR-INT-01: KPIs configuráveis com fórmula, fonte, owner, versão e freshness.
- HR-INT-02: drill-down até aos factos autorizados.
- HR-INT-03: previsto e realizado com rótulos diferentes.
- HR-INT-04: alertas com owner, SLA, estado, explicação e resultado.
- HR-INT-05: contestação/correcção de factos usados numa decisão.
- HR-INT-06: model governance e human-in-the-loop.

### 11.7 Self-service e reporting

- HR-ESS-01: colaborador consulta perfil, ponto, saldo, pedido e recibo próprios.
- HR-ESS-02: colaborador solicita correcção sem editar o facto.
- HR-ESS-03: gestor vê equipa dentro do scope, sem exposição salarial.
- HR-REP-01: headcount, custo, absentismo e capacidade por dimensão autorizada.
- HR-REP-02: relatórios legais e de auditoria reproduzíveis.
- HR-REP-03: exportação assíncrona, auditada, cifrada e com expiração.

### 11.8 Planeamento de workforce

- HR-WFP-01: versionar plano, cenário, premissas, FTE, custo e skills demand.
- HR-WFP-02: controlar posição por budget, período, ocupação e vacancy.
- HR-WFP-03: reconciliar headcount planeado, forecast e realizado.
- HR-WFP-04: aprovar criação/congelamento de posição e override de budget.

### 11.9 Recrutamento e onboarding

- HR-TA-01: requisition nasce de posição/budget ou excepção aprovada.
- HR-TA-02: gerir candidatura e scorecards sem expor atributos protegidos.
- HR-TA-03: garantir consentimento, retenção e candidate self-service.
- HR-TA-04: oferta versionada com approval e assinatura.
- HR-ONB-01: converter candidato aceite em pre-hire sem duplicar pessoa.
- HR-ONB-02: journeys cross-functional com dependência, SLA e evidência.
- HR-ONB-03: medir readiness e concluir onboarding antes do fecho.

### 11.10 Learning e desenvolvimento

- HR-LRN-01: catálogo/versionamento, sessões e currículos.
- HR-LRN-02: inscrição, presença, conclusão e avaliação auditáveis.
- HR-LRN-03: compliance learning por posição e risco.
- HR-LRN-04: plano de desenvolvimento e recertificação.
- HR-LRN-05: skill inferida, declarada e verificada permanecem distintas.

### 11.11 Performance, carreira e sucessão

- HR-PRF-01: objectivos, check-ins, feedback, reviews e calibration.
- HR-PRF-02: avaliação guarda contexto, evidência, contestação e revisão.
- HR-PRF-03: compensation decision exige workflow separado.
- HR-CAR-01: career paths, mobilidade e oportunidades internas.
- HR-SUC-01: posições críticas, sucessores, readiness e development actions.
- HR-SUC-02: succession/talent pools possuem leitura auditada e acesso restrito.

### 11.12 Total rewards e benefícios

- HR-TRW-01: grades, ranges e compensation review budgets effective-dated.
- HR-TRW-02: mérito, promoção, bónus e incentivos com maker-checker.
- HR-TRW-03: benefícios por plano, provider, elegibilidade e enrolment.
- HR-TRW-04: dependentes/beneficiários usam minimização e retenção própria.
- HR-TRW-05: total rewards statement distingue valor garantido e potencial.

### 11.13 HR Service Delivery e engagement

- HR-SVC-01: catálogo de serviços, casos, tarefas, SLA e knowledge base.
- HR-SVC-02: intake omnicanal e routing sem expor caso confidencial.
- HR-SVC-03: employee journey liga casos a tarefas de outros módulos.
- HR-ENG-01: surveys e action plans com anonimato por coorte mínima.
- HR-ENG-02: nunca mostrar resposta individual quando prometido anonimato.

### 11.14 Relações laborais, saúde e segurança

- HR-ER-01: grievance/discipline/investigation com evidence chain e appeal.
- HR-ER-02: involved parties e testemunhas possuem need-to-know.
- HR-ER-03: denúncia anónima não tenta reidentificar o autor.
- HR-OHS-01: perigo, risco, incidente, near miss e corrective action.
- HR-OHS-02: fitness-for-work expõe apenas outcome operacional.
- HR-OHS-03: dados médicos ficam segregados do employee file comum.
- HR-OHS-04: incidentes operacionais podem referenciar TMS/Oficina sem copiar
  toda a investigação de segurança.

### 11.15 Trabalhadores contingentes

- HR-CWK-01: engagement, fornecedor, contrato, rate, assignment e end date.
- HR-CWK-02: contractor não é tratado como empregado para payroll/política sem
  classificação aprovada.
- HR-CWK-03: onboarding, acesso, tempo, safety e offboarding são aplicáveis.
- HR-CWK-04: total workforce reporting distingue employee e contingent.

## 12. Requisitos não funcionais

- HR-NFR-01: toda mutação crítica é transaccional e gera outbox/audit na mesma
  transacção.
- HR-NFR-02: APIs e workers são idempotentes nas fronteiras de retry.
- HR-NFR-03: cálculo com os mesmos snapshots/ruleset produz o mesmo hash.
- HR-NFR-04: dinheiro usa `Decimal/Numeric`, moeda e política de arredondamento;
  nunca `float`.
- HR-NFR-05: timestamps são timezone-aware; calendário declara timezone local.
- HR-NFR-06: disponibilidade suporta cache tenant-scoped com invalidação por
  versão e fallback seguro.
- HR-NFR-07: projections suportam rebuild, checkpoint e reconciliação.
- HR-NFR-08: payroll, PII e documentos não entram em telemetry/logs sem
  mascaramento.
- HR-NFR-09: backups, restore e DR preservam a cadeia de payroll/audit.
- HR-NFR-10: acessibilidade, português de Moçambique e formatos locais são
  validados com utilizadores.
- HR-NFR-11: SLOs, RPO/RTO e retenção são aprovados antes do piloto e medidos em
  produção; presença de código não prova o SLO.
- HR-NFR-12: alterações de schema seguem expand/contract e suportam rollback de
  aplicação sem perda de factos.

Metas iniciais a validar no ADR operacional:

- decisão de disponibilidade p95 abaixo de 300 ms em carga nominal;
- zero duplicação em replay de evento, cálculo, posting e pagamento;
- 100% dos runs fechados reproduzíveis pelo hash e ruleset;
- RPO de dados transaccionais <= 15 minutos e RTO <= 4 horas;
- exports sensíveis expiram e deixam trilho de acesso;
- nenhum endpoint devolve campo salarial sem capacidade específica.

## 13. UX principal

### Colaborador

- “Meu perfil” com pedidos de correcção;
- ponto/turno e estado de sincronização;
- saldo e pedidos de ausência;
- recibos e comprovativos;
- documentos/certificações e alertas;
- canal de contestação.

### Gestor

- equipa, escala, capacidade e bloqueios explicados;
- pedidos pendentes;
- gaps de skills/certificações;
- desempenho contextual, sem salário;
- alertas de carga/fadiga com acção sugerida.

### RH

- organograma e headcount;
- admissão/lifecycle/timeline;
- contratos, compensação e documentos;
- férias, excepções e compliance;
- offboarding.

### Payroll/Finanças

- calendário e checklist do período;
- qualidade/reconciliação dos inputs;
- simulação e comparação;
- run, validação, aprovação, posting e pagamento;
- outputs legais, recibos e evidência;
- reconciliação com diário e banco.

## 14. Migração do scaffold actual

### 14.1 Estratégia

Usar expand/contract:

1. inventariar dados e congelar invariantes;
2. criar novas tabelas sem remover as antigas;
3. introduzir IDs canónicos e adapters;
4. backfill idempotente com relatório por linha;
5. dual-read/compare em janela controlada;
6. mudar writes por aggregate;
7. reconciliar contagens, somas e hashes;
8. desactivar payroll legado;
9. remover campos/tabelas apenas em release posterior com rollback provado.

### 14.2 Mapeamento

| Legado | Alvo | Tratamento |
| --- | --- | --- |
| `employees` dados pessoais | `people` + `worker_profiles` | normalizar e marcar provenance |
| `employees.role/department` | job/position/org assignment | mapping aprovado ou fila de excepção |
| `employees.base_salary` | compensation version/component | vigência inferida sinalizada, nunca silenciosa |
| `employees.irps_tax_percentage` | legal input/ruleset | não migrar como regra fiscal universal |
| `employees.driver_id` | operational role link | validar mesmo tenant e unicidade |
| `employees.user_id` | identity link | validar lifecycle e revogação |
| `employee_documents` | typed document/evidence | validar storage, classificação e validade |
| `absences` | leave case + ledger events | reconciliar intervalo, aprovação e pagamento |
| `payroll_slips/lines` | imported legacy calculation | preservar como histórico não certificado |
| `salary_advances` | receivable/deduction schedule | reconciliar saldo e estado contabilístico |

Dados sem evidência suficiente vão para `migration_exception`; não recebem
defaults inventados.

### 14.3 Bloqueios de produção

Até concluir a migração:

- endpoint legado de geração de payroll não processa tenant real;
- nenhuma folha `draft` cria diário finalizado;
- nenhum valor fiscal hard-coded é apresentado como certificado;
- backfill e rollback passam em cópia de base histórica e base vazia;
- totais por trabalhador/período reconciliam ou possuem excepção assinada.

## 15. Plano de entrega

| ID | Entrega | Depende de | Evidência | Gate |
| --- | --- | --- | --- | --- |
| HRM-00 | ADR de boundaries, threat model, legal matrix e data classification | G0-G3 + ERP-00 | ADRs, parecer funcional e contratos aprovados | H0 |
| HRM-01 | Organization, Person, Worker, Employment, Job e Position | ERP-03/04 | migration, CRUD, temporal invariants e RLS real | H1 |
| HRM-02 | Workforce planning, position control e headcount budget | HRM-01 + ERP planning | cenário, approval e plan-vs-actual | H1 |
| HRM-03 | Talent acquisition, candidate portal e offer | HRM-01/02 | requisition-to-offer E2E, fairness e retenção | H2 |
| HRM-04 | Onboarding, journeys e workforce lifecycle | HRM-01/03 + IAM/Assets | pre-hire-to-productive e offboarding E2E | H2 |
| HRM-05 | Compensation, benefits e total rewards | HRM-01/02 | review cycle, eligibility e maker-checker | H2 |
| HRM-06 | Calendário, escalas, ponto, férias e disponibilidade | HRM-01 | offline/replay/leave ledger/reconciliação | H3 |
| HRM-07 | Skills, learning e certificações | HRM-01/04 | learning/compliance/recertification E2E | H3 |
| HRM-08 | Goals, performance, feedback e calibration | HRM-01/07 | ciclo E2E, contestação e bias controls | H4 |
| HRM-09 | Career, mobility, talent review e succession | HRM-02/07/08 | critical-role coverage e mobility E2E | H4 |
| HRM-10 | HR Service Delivery, knowledge e employee journeys | HRM-01/04 | case SLA, privacy e service analytics | H4 |
| HRM-11 | Engagement, employee relations, OHS e wellbeing | HRM-01/10 | anonymity, investigation e safety E2E | H4 |
| HRM-12 | Envelope, outbox/inbox e adapters corporativos | HRM-01 + WKS-04 | contract, replay, backfill e DLQ | H3 |
| HRM-13 | Rule engine, inputs e payroll run FSM | HRM-05/06/12 + ERP-09 | golden cases, memória e hash | H5 |
| HRM-14 | Posting, tesouraria, pagamento e outputs legais | HRM-13 + ERP-10 | payroll-ledger-bank reconciliado | H5 |
| HRM-15 | Candidate, employee, manager e HR workspaces | HRM-03..14 | journeys por persona, field auth e WCAG | H5 |
| HRM-16 | Human capital reporting, KPI catalog e workforce analytics | HRM-02..12 + BI-01/02 | ISO-aligned metrics, rebuild e drill-down | H6 |
| HRM-17 | HR Intelligence e model governance | HRM-16 + BI-06/08 | fairness, red-team, appeal e kill switch | H6 |
| HRM-18 | Migração, piloto, DR e certificação enterprise HRM | HRM-00..17 | lifecycle completo e sign-offs | H7 |

Trabalho preparatório pode ser paralelo; promoção respeita:

```text
H0 Architecture & Legal Baseline
  -> H1 Core & Workforce Strategy
  -> H2 Attract, Join & Reward
  -> H3 Workforce Operations & Learning
  -> H4 Talent, Experience & Relations
  -> H5 Certified Payroll & Workspaces
  -> H6 Human Capital Analytics & Responsible AI
  -> H7 Enterprise Pilot & Production Evidence
```

## 16. Gates de aceitação

### H0 — Architecture & Legal Baseline

- bounded contexts, ownership e APIs aprovados;
- matriz legal tem owner, fonte, vigência e processo de mudança;
- threat model e classificação de dados aprovados;
- decisão sobre entidades legais, calendários, moeda e centros de custo;
- plano expand/contract e rollback revistos.

### H1 — Core & Workforce Strategy

- dois tenants usam identificadores sobrepostos sem leitura/inferência cruzada;
- pessoa, vínculo, cargo, posição e remuneração não estão fundidos;
- vigência e sobreposição possuem constraints/testes;
- alterações críticas deixam timeline e audit;
- desligamento revoga acesso sem apagar histórico.
- position control rejeita ocupação/recrutamento sem budget ou override;
- plano, forecast, cenário e realizado são entidades distintas;
- empregados e contingentes são classificados e reportados separadamente.

### H2 — Attract, Join & Reward

- requisition nasce de posição/headcount aprovado;
- candidato percorre candidatura, avaliação, oferta e pre-hire com privacidade;
- scoring tem critérios estruturados, fairness e decisão humana;
- onboarding orquestra RH, gestor, IAM, activos, safety e learning;
- compensation review respeita budget, range e maker-checker;
- benefícios aplicam elegibilidade effective-dated sem excesso de PII.

### H3 — Workforce Operations & Learning

- ponto offline sincroniza sem perder/duplicar evento;
- correcção preserva original e maker-checker;
- saldo de férias reconcilia com ledger;
- TMS/Oficina recebem decisão explicada e não atribuem inelegível;
- replay, evento fora de ordem, DLQ e rebuild passam;
- certificação expirada bloqueia quando obrigatória.
- learning obrigatório, conclusão, validade e recertificação reconciliam;
- tempo e disponibilidade funcionam para qualquer job profile, não apenas
  motoristas e técnicos.

### H4 — Talent, Experience & Relations

- objectivos, check-ins, review, calibration e appeal completam o ciclo;
- performance usa contexto e não converte produtividade em punição automática;
- career paths, mobility, talent pools e succession têm critérios e acesso
  auditáveis;
- HR cases cumprem routing, SLA, confidencialidade e knowledge governance;
- surveys respeitam anonimato por limiar;
- employee relations preserva evidence chain e direito de resposta;
- OHS liga hazard, incidente, investigação e corrective action;
- dados médicos e denúncias permanecem segregados.

### H5 — Certified Payroll & Workspaces

- casos dourados e cálculo independente coincidem;
- ruleset, inputs, memória e hash reproduzem cada recibo;
- preparador não aprova o próprio run;
- diário só é criado depois de aprovação;
- payroll, ledger, tesouraria, banco e outputs legais reconciliam;
- retry não duplica linha, desconto, posting, pagamento ou submissão;
- ajustes não alteram período fechado;
- contabilista/jurista local assinam a matriz aplicável ao piloto.
- candidate, employee, manager e HR workspaces passam journeys e WCAG;
- field-level authorization impede inferência salarial e de casos restritos.

### H6 — Human Capital Analytics & Responsible AI

- cada KPI tem fórmula, fonte, versão, owner, freshness e drill-down;
- factos reconciliam com TMS/Oficina/HRM;
- previsão/recomendação não aparece como facto;
- nenhuma decisão laboral adversa é autónoma;
- fairness, drift, contestação, fallback e kill switch são provados;
- cross-tenant analytics não permite reidentificação.
- workforce composition, cost, recruitment, mobility, turnover, skills,
  wellbeing, safety, relations, culture e engagement têm métricas auditáveis;
- AI assistiva nunca decide contratação, salário, promoção, disciplina ou saída.

### H7 — Enterprise Pilot & Production Evidence

- tenant piloto percorre workforce plan -> recruit -> onboard -> develop ->
  review -> reward -> payroll -> mobility/exit com pessoas autorizadas reais;
- segundo tenant controlado prova isolamento na mesma janela;
- jornadas de candidato, colaborador, gestor, RH, recruiter, talent, payroll,
  tesouraria, ER/OHS e auditor passam;
- migração histórica, backup/restore, DR, carga e observabilidade passam;
- incidentes e excepções estão fechados ou formalmente aceites;
- Produto, RH, Legal, Finanças, Segurança, Engenharia e Operações assinam o
  ledger GO/NO-GO.

Qualquer gate vermelho mantém a capacidade correspondente em `NO-GO`. H5
vermelho impede payroll real; H7 vermelho impede declarar o HRM enterprise pronto,
mesmo que UI, CRUD ou módulos isolados estejam verdes.

## 17. Testes obrigatórios

### Domínio e propriedades

- transições válidas/inválidas de todas as FSMs;
- intervalos temporais, fronteiras de vigência e sobreposições;
- arredondamento, escalões, bases, caps e mudança de regra no meio do período;
- invariantes de dinheiro e diário balanceado;
- property-based tests de regras e ajustes;
- recontratação, transferência, múltiplas posições e término retroactivo.

### Segurança

- matriz por capacidade, scope organizacional e campo;
- RLS com role restrita `NOBYPASSRLS`;
- 404 cross-tenant, inclusive ficheiro, cache, export, evento e worker;
- tentativa de IDOR, enumeração, CSV injection e export massivo;
- break-glass, expiração, auditoria e revogação;
- logs/telemetry sem PII ou payroll.

### Integração e concorrência

- outbox/inbox atómico;
- replay, duplicação, atraso, ordem trocada, schema incompatível e DLQ;
- dois aprovadores concorrentes;
- cálculo/posting/pagamento concorrente e retry;
- rebuild de availability/KPI e reconciliação.

### Migração

- `alembic upgrade head` em base vazia;
- upgrade em snapshot histórico e `alembic check`;
- backfill repetido sem duplicação;
- contagens, relações, valores e hashes reconciliados;
- rollback de aplicação e migration ensaiado.

### Jornadas reais

- admissão a primeiro recibo;
- motorista: escala -> elegibilidade -> viagem -> variável -> payroll;
- mecânico: tarefa -> tempo/QC/retrabalho -> variável -> payroll;
- férias com conflito de demanda e decisão;
- correcção de ponto após inputs locked;
- desligamento com acesso, activos, pagamento final e histórico;
- run normal, suplementar, reversão, pagamento e reconciliação.

## 18. Métricas de sucesso

Baselines `X/Y` devem ser medidos no Sprint 0. Não se inventam metas sem baseline.

- tempo de fecho do payroll;
- percentagem de inputs reconciliados antes do lock;
- número e valor de ajustes pós-fecho;
- taxa de runs reproduzíveis;
- divergência payroll-ledger-bank;
- prazo de resolução de ponto/ausência;
- adopção de self-service;
- cobertura de documentos/certificações válidos;
- atribuições operacionais bloqueadas antes de incumprimento;
- qualidade/freshness dos eventos;
- taxa de alertas úteis, contestados e falsos positivos;
- incidentes de acesso indevido e cross-tenant.

## 19. Fora de âmbito inicial

- marketplace público de candidatos partilhado entre tenants;
- autoria avançada SCORM/xAPI e streaming próprio; o HRM integra conteúdo;
- administração clínica e prontuário médico;
- corretora/seguradora própria de benefícios;
- compensação de equity;
- payroll multi-país antes de certificar Moçambique;
- decisões disciplinares ou de despedimento automáticas;
- reconhecimento facial obrigatório;
- benchmarking cross-tenant sem programa formal de privacidade.

Talent Acquisition, Onboarding, Learning, Benefits, Performance, Mobility,
Succession, HR Service Delivery, Employee Relations e OHS fazem parte do HRM
enterprise. Podem ser entregues por fases ou adapters buy-vs-build, mas não são
tratados como extensões opcionais da visão.

## 20. Decisões pendentes antes de HRM-00

1. entidades legais e filiais exactas do tenant piloto;
2. calendário, categorias, convenções colectivas e políticas internas;
3. fontes oficiais e especialista que assinará cada regra legal;
4. hardware/canais de ponto e política de geolocalização;
5. periodicidade, moeda, centros de custo e contas de payroll;
6. níveis de aprovação de férias, compensação, payroll e pagamento;
7. política de retenção por categoria documental;
8. requisitos exactos dos ficheiros/submissões AT e INSS;
9. população, período e critérios de sucesso do piloto;
10. SLO, RPO/RTO e janela de manutenção acordados.

## 21. Definition of Done

O HRM é “robusto e impecável” apenas quando:

- o domínio e os contratos estão implementados sem duplicar ownership;
- os gates H0–H7 possuem evidência executável e sign-off;
- payroll real é legalmente validado e reproduzível;
- isolamento funciona abaixo da API;
- migração e reconciliação fecham sem defaults silenciosos;
- jornadas reais passam sem mocks;
- observabilidade, backup, restore, DR e suporte estão operacionais;
- analytics permanece derivado, explicável e incapaz de executar decisão laboral
  adversa por conta própria.

Até lá, a classificação correcta é `implementação parcial` ou
`engenharia validada localmente`, nunca `certificado para produção`.
