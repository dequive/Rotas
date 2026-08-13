# ROTAS Engineering Standards

Estas normas sao obrigatorias para a materializacao do ROTAS. O objectivo e construir um produto robusto, auditavel, evolutivo e seguro para operacao real de frotas em Mocambique.

## Principios Base

- O dominio manda na tecnologia: carga, viagens, documentos, descarga e cobranca contratual devem estar modelados explicitamente.
- Combustivel, oficina, pecas e ferramentas sao dominios operacionais de primeira classe quando afectam disponibilidade, custo ou margem.
- O MVP deve ser simples, mas nao descartavel.
- Cada decisao tecnica deve reduzir risco operacional, risco financeiro ou risco de manutencao futura.
- Tudo que afecta cobranca, auditoria, seguranca ou disponibilidade deve ter teste automatizado.
- Dados de operacao nao devem ser apagados fisicamente sem politica clara; usar estados, auditoria e anulacao controlada.

## Governanca obrigatoria: Issue -> PR -> Deploy

Este contrato foi introduzido pela
[Issue #23](https://github.com/dequive/Rotas/issues/23). Nenhuma correccao,
melhoria, nova funcao, refactor, dependencia, migracao,
infraestrutura ou alteracao documental comeca sem uma GitHub Issue. A Issue e o
registo canonico de problema, escopo e aceite; o PR e o registo canonico de revisao e
evidencia; o deploy e a promocao de um SHA imutavel ja revisto.

1. Criar a Issue com o template `Task` e classificar como `correction`,
   `improvement` ou `feature`.
2. Registar contexto, fora de escopo, criterios de aceite, riscos, estados UX,
   telemetria, plano de testes, rollout e rollback.
3. Criar uma branch curta e um PR dedicado. O corpo do PR deve conter
   `Closes #<numero>` e evidencias reproduziveis dos gates aplicaveis.
4. Exigir CI verde, revisao, CODEOWNERS, conversas resolvidas e aprovacao independente
   conforme `infra/release/PR00_RELEASE_GOVERNANCE.json`.
5. Fazer deploy apenas do merge/release SHA. Registar ambiente, artefacto/digest,
   migracao, smoke tests, SLOs/alertas observados e decisao GO/NO-GO.
6. Fechar a Issue apenas depois da verificacao pos-deploy. Merge nao e sinonimo de
   deploy; implementado localmente nao e sinonimo de certificado em runtime.

Emergencias podem usar um fluxo abreviado, mas exigem Issue, PR, aprovacao, rollback e
post-mortem. Push directo e deploy de working tree sao proibidos. As templates
canonicas vivem em `.github/ISSUE_TEMPLATE/task.yml` e
`.github/pull_request_template.md`; o gate de ligacao Issue/PR vive em
`.github/workflows/engineering-governance.yml`.

## SOLID

### Single Responsibility Principle

- Cada modulo de produto tem uma responsabilidade operacional clara: Centro de Comando, Frota e Pessoas, Transporte e Carga, Custos e Margem, Combustivel, Oficina e Manutencao, Cobranca, Administracao Operacional e Suporte Tecnico-Operacional.
- Pacotes tecnicos backend podem ser mais granulares que os modulos de produto quando isso reduz acoplamento ou protege regras de dominio.
- Routers cuidam apenas de HTTP: entrada, dependencias e resposta.
- Services coordenam casos de uso.
- Domain functions guardam regras puras de negocio.
- Models representam persistencia, nao devem conter fluxos de aplicacao complexos.

### Open/Closed Principle

- Novos tipos de documento de carga devem ser adicionados por configuracao/tipos, sem reescrever cobranca.
- Novos canais de alerta devem entrar por adaptadores: dashboard, WhatsApp, email, SMS.
- Novos centros de custo devem ser extensoes do modelo de custos, nao campos soltos espalhados.
- Novos tipos de movimento de stock devem ser extensoes controladas do livro de movimentos, nao actualizacoes directas ao saldo.

### Liskov Substitution Principle

- Interfaces/adaptadores devem ser substituiveis sem mudar casos de uso.
- Um storage local, R2 ou filesystem de testes deve cumprir o mesmo contrato.
- Um emissor WhatsApp fake em testes deve poder substituir o emissor real.

### Interface Segregation Principle

- O PWA motorista nao deve depender de interfaces de gestor.
- O dashboard nao deve receber endpoints desenhados para sincronizacao offline.
- Servicos externos devem ter interfaces pequenas e especificas: upload, notificar, cobrar, exportar.

### Dependency Inversion Principle

- Regras de negocio nao dependem directamente de FastAPI, SQLAlchemy, WhatsApp ou R2.
- Casos de uso dependem de contratos/repositories; infra implementa esses contratos.
- Integracoes externas ficam nas bordas do sistema.

## Arquitectura

- Monolito modular no MVP, com limites internos fortes.
- Cada modulo deve ter `models.py`, `schemas.py`, `router.py`, `service.py` e, quando houver regra critica, `domain.py`.
- Cada modulo e um pacote com interface publica minima. Outros modulos nao devem importar detalhes internos sem necessidade.
- Acesso entre modulos deve acontecer por services, domain contracts ou repositories publicos. Evitar acoplar `billing` directamente a detalhes ORM de `cargo` e `trips`.
- Evitar microservicos prematuros; separar por modulo primeiro, extrair servico so quando houver necessidade operacional real.
- Toda tabela de tenant deve ter `tenant_id` indexado.
- Tabelas operacionais que afectam disponibilidade, stock, custo ou cobranca devem ter estados explicitos e historico auditavel.
- Veiculos e motoristas devem ter historicos detalhados, separados e tenant-scoped; quando um evento envolve ambos, cada historico referencia o outro actor sem fundir as trilhas.
- Endpoints devem resolver tenant pelo token/middleware; nunca confiar em `tenant_id` enviado pelo cliente comum.
- API publica deve ser versionada em `/api/v1`. Mudancas incompativeis exigem nova versao ou periodo de compatibilidade.
- PWA offline pode ficar desactualizada; endpoints usados pelo motorista devem manter compatibilidade por pelo menos duas versoes menores.

## Backend

- Usar FastAPI com Pydantic para contratos de entrada/saida.
- SQLAlchemy 2.0 async para runtime da API.
- Alembic para todas as mudancas de schema.
- Services nao devem devolver ORM cru em fluxos publicos sem schema de resposta.
- Erros devem usar envelope consistente, sem vazar stack trace para cliente.
- Idempotencia obrigatoria para sync offline e uploads vindos do PWA.
- Operacoes idempotentes devem receber `Idempotency-Key`, `device_id`, `entity_type`, `operation` e hash do payload.
- Se a mesma chave chegar com o mesmo hash, devolver a resposta anterior.
- Se a mesma chave chegar com hash diferente, rejeitar com conflito e manter auditoria.
- Chaves de idempotencia devem ser mantidas por janela minima de 30 dias para entidades operacionais e 90 dias para entidades de cobranca.

## Frontend Gestor

- Interface deve ser operacional, densa, clara e orientada a decisao.
- Evitar ecras decorativos ou marketing no produto.
- Estados de loading, progresso/pending, vazio, dados parciais/degradados, erro,
  permissao negada e sucesso devem existir em todos os fluxos reais onde se aplicam.
- O primeiro carregamento usa skeleton que preserva a geometria do conteudo; spinner
  isolado e reservado a accoes curtas e locais. Operacoes mensuraveis mostram progresso
  real; quando nao mensuraveis, mostram estado indeterminado e texto da operacao.
- Rotas, modais pesados, graficos, editores, media e listas extensas usam lazy loading
  quando isso reduz o caminho critico. Reservar dimensoes evita layout shift. Conteudo
  essencial, foco, erros e confirmacao da accao nunca dependem de lazy loading tardio.
- Movimento segue `DESIGN.md` e a skill Design Motion Principles. Para o SaaS ROTAS,
  Emil Kowalski e a lente primaria (proposito, frequencia e rapidez) e Jakub Krehel a
  secundaria (polimento discreto de producao).
- Nao se anima cada elemento. Toda mudanca perceptivel de estado tem feedback, mas
  accoes frequentes ou iniciadas por teclado sao instantaneas. Transicoes ocasionais
  sao interrompiveis, em geral 180-250 ms e nunca decorativas por defeito.
- Animar apenas `transform`, `opacity` e, com parcimonia, `filter`; nunca propriedades de
  layout. Saidas sao mais subtis que entradas, curvas sao explicitas e bounce e zero em
  fluxos empresariais. `prefers-reduced-motion` e um caminho funcional sem movimento
  sao obrigatorios e testados.
- Tabelas de operacao devem permitir filtro por periodo, cliente, viatura, motorista, contrato e estado de cobranca.

## PWA Motorista

- Offline-first e obrigatorio.
- Escrever primeiro localmente; sincronizar depois.
- Mostrar estado de sincronizacao de forma simples.
- Fotos devem ser comprimidas antes do upload.
- Accoes criticas devem ter prova: GPS, timestamp, foto/documento e responsavel.
- UX deve funcionar em Android barato, ecras pequenos e rede instavel.
- Skeletons, lazy loading e movimento devem ser testados num perfil de dispositivo de
  baixo desempenho. O feedback offline/sync tem prioridade sobre animacao decorativa.

## Dominio de Carga e Cobranca

- Contrato de prestacao de servicos e entidade de primeira classe.
- O MVP usa viagem primeiro com contrato opcional como fluxo principal, preservando suporte a contrato primeiro para clientes maduros.
- Load Permit/Autorizacao de Carregamento e documento emitido pelo cliente, nao pelo transportador; o ROTAS rastreia e valida o registo.
- Manifesto de Carga e obrigatorio quando o transportador emite documento para produtos manufaturados.
- Documento de descarga/prova de entrega valida a cobranca apenas apos validacao do gestor no MVP.
- Para cliente empresa, prova preferencial e guia carimbada/assinada ou documento de descarga emitido pelo cliente.
- Para cliente individual, prova alternativa pode ser foto/GPS, assinatura/codigo ou excepcao manual auditada.
- Viagem carregada num mes e descarregada no mes seguinte entra na cobranca do mes da descarga.
- Uma viagem nao deve ser facturada sem prova de descarga, salvo excepcao aprovada e auditada.
- Toda viagem contratual deve indicar estado de carga: carregado/vazio, vazio/carregado, carregado/carregado, vazio/vazio ou equivalente operacional.
- Itens de cobranca devem manter ligacao a viagem, cliente, contrato, Load Permit, manifesto/guia e documento de descarga.
- Uma viagem contratual deve estar ligada a `contract_id` e manter `contract_reference` como referencia legivel/auditavel.
- Viagem sem contrato deve poder existir, mas deve carregar estado operacional que indique pendencia de enquadramento contratual quando for carga de cliente.
- `billing_item` so deve ser criado quando houver contrato associado e prova de descarga validada.
- Alteracoes em valor cobrado, periodo ou prova de entrega devem gerar evento de auditoria.

## Dominio de Combustivel

- Combustivel interno deve ser controlado por movimentos, nao por actualizacao directa de saldo.
- `fuel_tanks.current_stock_liters` pode existir para leitura rapida, mas a fonte de verdade deve ser `fuel_movements`.
- Compra de combustivel nao aumenta stock ate existir recepcao verificada ou ajuste autorizado.
- Soma de recepcoes verificadas nao pode ultrapassar a quantidade aprovada na compra.
- Saida de combustivel para viatura deve validar tanque, stock suficiente, viatura, motorista, litros, odometro e responsavel.
- Custo da saida interna deve usar custo medio ponderado do tanque para alimentar custo real da viagem.
- Abastecimento sem viagem associada e permitido apenas quando justificado, mas deve poder gerar exception operacional.
- Divergencia entre stock fisico e teorico acima da tolerancia deve gerar exception.
- Todo ajuste de stock deve exigir permissao, motivo e auditoria.
- Quem regista abastecimento nao deve aprovar ajuste de stock.

## Dominio de Oficina, Pecas e Ferramentas

- Ordem de servico activa deve afectar disponibilidade da viatura.
- Viatura em manutencao nao deve ser atribuida a nova viagem sem waiver aprovado e auditado.
- Pecas devem ser controladas por movimentos; stock nao deve ser alterado directamente.
- Ferramentas devem ser controladas por checkout/devolucao, nao por consumo.
- Ferramenta danificada, perdida, reformada ou com calibracao vencida deve bloquear checkout quando for critica.
- Mecanico executa tarefas, mas libertacao operacional da viatura deve obedecer permissao/politica do tenant.
- Avaria em viagem deve poder criar maintenance request e alimentar custo real da viagem.

## Disponibilidade e Torre de Controlo

- Disponibilidade de viatura e motorista deve ser derivada de viagens activas, dispatch, manutencao, compliance, bloqueios e waivers.
- O sistema deve gerir por excepcoes operacionais, nao apenas por relatorios.
- Excepcoes devem ligar sempre a entidade origem e ter estado: aberta, reconhecida ou resolvida.
- Risco aceite nao deve ser escondido como ignorado; deve ser representado por waiver aprovado e auditado.
- Boards devem consumir services agregadores, evitando duplicar regras de estado no frontend.

## Testes

- Regras de negocio criticas devem ter testes unitarios puros.
- Casos de uso devem ter testes de service com repositorios fake ou base de teste.
- Endpoints criticos devem ter testes de API.
- Sync offline deve ter testes de idempotencia e reenvio.
- Fluxos financeiros devem testar limites de periodo, duplicacao, cancelamento e estados de cobranca.
- Fluxos de concorrencia devem testar duas submissoes simultaneas para a mesma viatura, viagem ou idempotency key.
- Antes de piloto com frota real, testar pico de sync quando varias viaturas regressam a base e enviam filas offline ao mesmo tempo.
- Frontends usam Vitest/Testing Library para unidade e integracao e Playwright para E2E,
  acessibilidade, reduced-motion, loading/progresso e jornadas criticas.
- Backend e Governance usam pytest para unidade, service/API, integracao, migracao e
  isolamento multitenant. Testes que dizem usar uma base real devem provar a role e RLS.
- Coverage e publicado no Codecov por componente. Coverage e sinal de risco, nao prova
  de qualidade: limiares nao podem cair no PR e modulos financeiros, autenticacao,
  tenant/RLS, sync/idempotencia e migracoes exigem cobertura de branches critica.
- Stryker e a ferramenta canonica de mutation testing TypeScript/JavaScript (o nome e
  `Stryker`, nao `Stryke`). Executa incrementalmente em PRs de dominio critico e em suite
  alargada agendada; mutantes sobreviventes exigem teste, justificacao ou Issue.

## Seguranca

- JWT com refresh tokens e rotacao futura.
- Passwords sempre com hash forte.
- Segredos apenas em `.env`, nunca em codigo.
- RLS no PostgreSQL como defesa adicional ao service layer.
- Uploads devem validar MIME, tamanho, hash e permissao.
- Dados sensiveis de motoristas devem ser tratados como dados pessoais.

## Observabilidade

- Logging estruturado por `tenant_id`, `user_id`, `driver_id`, `trip_id` quando aplicavel.
- Cada sync batch deve ter correlation id.
- Erros de integracao externa devem ser rastreaveis sem expor segredos.
- Alertas operacionais devem distinguir falha tecnica de problema de negocio.
- Metricas minimas: latencia por endpoint, taxa de erro por modulo, tamanho da fila offline, tempo medio de sync, falhas de upload e falhas de notificacao.
- Alertas tecnicos do sistema nao devem ser misturados com alertas operacionais de frota no mesmo dominio de codigo.
- OpenTelemetry e o contrato canonico para traces, metricas e correlacao de logs entre
  Manager, Driver, API, workers, Governance e integracoes. Propagar W3C Trace Context e
  baggage apenas com atributos allowlisted e de baixa cardinalidade.
- Sentry e obrigatorio para erro, crash e performance onde ja integrado, sempre com
  scrub de PII/segredos, release SHA e environment. Um DSN ausente desactiva o exportador
  sem alterar o comportamento de negocio.
- Datadog e New Relic sao destinos suportados atraves de OTLP/OpenTelemetry Collector,
  nao agentes paralelos sempre activos. A escolha/activacao por ambiente requer Issue,
  avaliacao de custo/retencao/residencia de dados, teste de exportacao e rollback.
- E proibido enviar payloads, tokens, cookies, salarios, dados medicos, documentos,
  coordenadas precisas ou IDs humanos/tenant crus. Preferir IDs tecnicos correlacionaveis
  e hashing/normalizacao aprovados.
- A prova minima de runtime inclui trace ponta a ponta, erro correlacionado no Sentry,
  metricas/SLO, log correlacionado, alerta entregue/ack/resolvido e verificacao de scrub.

## Integracoes Externas

- WhatsApp deve ter fallback SMS para alertas criticos quando entrega falhar ou API estiver indisponivel.
- M-Pesa/e-Mola devem usar fila de retry com estados explicitos: `pending`, `sent`, `confirmed`, `failed`, `expired`.
- Todas as chamadas externas devem ter timeout, retry controlado e circuito de falha onde fizer sentido.
- Nenhuma integracao externa deve bloquear submissao local/offline do motorista.

## Riscos Operacionais Obrigatorios

- Motorista nao pode ter duas viagens activas conflitantes sem autorizacao explicita.
- Viatura nao pode estar activa em duas viagens sobrepostas sem aprovacao e auditoria.
- Migracoes de producao devem seguir estrategia expand/contract para reduzir downtime.
- Fotos e GPS devem ser validados por plausibilidade server-side sempre que possivel.
- Divergencia entre documento emitido pelo cliente e documento submetido pelo motorista deve criar estado de disputa, nao substituicao silenciosa.

## Qualidade e Revisao

- Codigo deve passar lint, typecheck e testes antes de ser considerado pronto.
- Mudancas de schema devem vir com migracao Alembic.
- Toda regra de cobranca deve ter criterio de aceite documentado.
- Evitar duplicacao prematura, mas extrair regra quando ela for partilhada por API, dashboard e PWA.
- Preferir nomes explicitos do dominio a nomes genericos.
- Contratos de arquitectura bloqueiam importacoes proibidas, ciclos e fuga de ORM/regras
  entre bounded contexts. `test_module_guard.py` e o baseline Python; o gate `arch-contract`
  deve cobrir tambem os workspaces TypeScript.
- Biome e o linter/formatter canonico TypeScript/JavaScript; TypeScript continua a ser o
  gate de tipos. Ruff e Pyright continuam canonicos em Python.
- Commitlint valida commits Conventional Commits e o historico do PR. Squash/merge deve
  conservar Issue e intencao no titulo/mensagem.
- Knip bloqueia exports, ficheiros e dependencias nao usados, com allowlist curta,
  comentada, temporaria e ligada a Issue.
- Dependencias e configuracoes de Biome, Commitlint, Knip, Stryker e Codecov devem ser
  fixadas no lockfile e executadas em CI; citar uma ferramenta neste documento nao a
  torna implementada.

## Definition of Done

- Implementacao compila.
- Testes relevantes passam.
- Linters/typecheck passam.
- Contrato API documentado por schema.
- Migracao criada quando houver schema novo.
- Fluxo documentado quando houver regra operacional nova.
- Auditoria/tenant/idempotencia considerados.
- Riscos e limitacoes conhecidos foram registados.
- Issue ligada, PR revisto e checks requeridos verdes.
- UX assincrona cobre skeleton/loading, pending/progresso, empty, partial/degraded,
  error/forbidden e success aplicaveis, incluindo reduced-motion e lazy loading sem CLS.
- Telemetria e alertas da mudanca foram exercitados sem PII; dashboard/runbook actualizado.
- Coverage nao regrediu e mutation testing foi executado quando o risco exige.
- Deploy/rollback e smoke tests foram registados para o mesmo SHA; a Issue so fecha apos
  verificacao pos-deploy.

## Estado de adopcao deste padrao em 2026-08-09

| Capacidade | Estado comprovado no checkout | Proximo gate |
|---|---|---|
| Governanca Issue -> PR -> Deploy | Template, workflow e CODEOWNERS implementados nesta cadeia; proteccao remota parcial e certificacao bloqueada | [Issue #31](https://github.com/dequive/Rotas/issues/31), [Issue #33](https://github.com/dequive/Rotas/issues/33) |
| UX assincrona e Motion Principles | Contrato definido; implementacao desigual entre rotas/componentes | [Issue #25](https://github.com/dequive/Rotas/issues/25) |
| Sentry | Parcial: Backend, Manager e Driver possuem SDK/configuracao e testes locais | validar evento e scrub por release SHA em staging |
| Prometheus, Alertmanager e Grafana | Implementado localmente; certificacao runtime PR-20 pendente | executar bundle PR-20 e janela SLO |
| OpenTelemetry | Apenas direccao/documentacao; sem instrumentacao/export OTLP comprovado | [Issue #26](https://github.com/dequive/Rotas/issues/26) |
| Datadog / New Relic | Nao configurados | [Issue #26](https://github.com/dequive/Rotas/issues/26), via OTLP e sem agentes duplicados |
| Ruff, Pyright, pytest, Vitest, Playwright | Configuracao e CI existentes, com cobertura desigual por jornada | preservar gates e fechar lacunas por Issue |
| Arch-contract | Parcial: guardas Python e verificadores de fronteira especificos | [Issue #27](https://github.com/dequive/Rotas/issues/27) |
| Biome, Commitlint, Knip | Nao configurados | [Issue #28](https://github.com/dequive/Rotas/issues/28) |
| Stryker | Nao configurado | [Issue #29](https://github.com/dequive/Rotas/issues/29) |
| Codecov / coverage thresholds | Nao configurados | [Issue #30](https://github.com/dequive/Rotas/issues/30) |

Esta tabela distingue implementacao local de certificacao. Nao promover uma linha para
"certificada" sem evidencia do ambiente, SHA e jornada descritos no gate correspondente.
