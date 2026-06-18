# ROTAS - Plano Mestre de Execucao

Versao: 0.2  
Data: 2026-05-28  
Objectivo: definir a base de sucesso para materializar o ROTAS sem dispersao, excesso de escopo ou decisoes tecnicas frageis.

## 1. Norte do Produto

O ROTAS deve resolver um problema concreto:

> Dar ao operador de frota controlo diario, auditavel e simples sobre viaturas, motoristas, checklists, combustivel e viagens, mesmo com internet instavel.

O MVP nao deve tentar ser "tudo para todos". Deve provar que uma frota pequena consegue operar melhor, perder menos informacao e reduzir fraude ou esquecimento usando o sistema todos os dias.

## 2. Principios Nao Negociaveis

1. Offline-first para o motorista
   - Se a app nao funcionar em rede instavel, o produto falha no contexto mocambicano.
   - Todo fluxo critico do motorista deve gravar localmente antes de tentar sincronizar.

2. Simplicidade operacional
   - Motorista nao pode enfrentar formularios longos e confusos.
   - Gestor deve ver rapidamente o que exige accao.

3. Auditabilidade
   - Registos criticos precisam de timestamp, user, tenant, fotos quando aplicavel e historico.
   - Alteracoes sensiveis devem gerar audit log.

4. Monolito modular no MVP
   - Nada de microservicos prematuros.
   - FastAPI modular com fronteiras claras por dominio.

5. Multi-tenancy desde o dia 1
   - Todas as entidades operacionais devem pertencer a um tenant.
   - O frontend nunca deve escolher tenant_id livremente em operacoes normais.

6. Fotos e provas como parte do fluxo
   - Recibos, odometro, estado da viatura, carga e incidentes precisam ser evidencias, nao anexos opcionais em fluxos criticos.

7. Produto primeiro, tecnologia depois
   - Cada funcionalidade deve responder a uma dor real do gestor ou motorista.
   - Evitar sofisticacao antes de validar uso real.

## 3. Definicao de Sucesso do MVP

O MVP e bem-sucedido se, em 30 dias de piloto:

- 2 a 3 clientes piloto usam o sistema com dados reais.
- Pelo menos 50 checklists reais sao submetidos.
- Pelo menos 30 abastecimentos reais sao registados com recibo/foto.
- Pelo menos 20 viagens sao abertas e fechadas.
- Zero perda de dados em modo offline testado.
- O gestor consegue responder diariamente:
  - Que viaturas estao activas?
  - Que checklists falharam ou estao em atraso?
  - Onde houve consumo anormal?
  - Que viagens estao em curso ou atrasadas?
  - Quanto cada viatura custou no periodo?
- Tempo medio de API em operacoes principais inferior a 500 ms em ambiente normal.
- Pelo menos 70% dos motoristas piloto conseguem completar checklist sem ajuda apos primeira demonstracao.

## 4. Escopo do MVP

### Incluido

- Autenticacao e tenants.
- Roles basicos: admin, manager, driver, viewer.
- Cadastro de viaturas.
- Cadastro de motoristas.
- Upload de fotos/documentos.
- Checklist pre-partida.
- Checklist chegada.
- Registo de abastecimento.
- Abertura e fecho de viagem.
- Autorizacao de Carregamento / Load Permit ligada a viagem ou trecho.
- Guia de transporte e outros documentos de carga ligados a viagem.
- Documento de descarga/entrega recebido pelo motorista ao descarregar mercadoria.
- Estado operacional da viagem: carregado/vazio, vazio/carregado, carregado/carregado, vazio/vazio.
- Manifesto de Carga quando o transporte envolver produtos manufaturados que exijam emissao pelo transportador.
- Base mensal de cobranca por contrato, usando documentos de carga e descarga como prova.
- Paragens simples de viagem.
- Alertas internos no dashboard.
- PWA motorista com armazenamento local.
- Sincronizacao basica com fila local.
- Relatorio mensal simples por viatura.

### Fora do MVP

- Marketplace de oficinas.
- Integracao real com seguradoras.
- Integracao real com financiadores.
- IA/ML para previsao avancada.
- Microservicos separados.
- App nativa React Native.
- Integracao completa com WhatsApp bidireccional.
- Pagamentos automaticos em producao.
- Relatorios oficiais INATTER sem validacao juridica.

## 5. Arquitectura Base

### ADRs Oficiais do MVP

ADR-001: Monolito modular

- Decisao: o MVP sera um monolito FastAPI modular.
- Motivo: reduz complexidade operacional, acelera entrega e preserva fronteiras por dominio.
- Consequencia: cada modulo tera routers, schemas, services e models proprios, mas deploy unico.

ADR-002: PWA com IndexedDB

- Decisao: a app do motorista sera PWA com IndexedDB/Dexie.js, nao SQLite.
- Motivo: IndexedDB e o storage nativo do browser; SQLite so entraria numa app nativa, Capacitor ou React Native.
- Consequencia: toda operacao critica do motorista deve gravar primeiro no browser e sincronizar depois.

ADR-003: Multi-tenancy com tenant_id + RLS

- Decisao: todas as tabelas operacionais terao tenant_id; RLS sera defesa adicional.
- Motivo: isolamento de clientes e seguranca SaaS desde o dia 1.
- Consequencia: o service layer sempre filtra por tenant; RLS nao substitui validacao da aplicacao.

ADR-004: Alertas internos antes de WhatsApp

- Decisao: MVP tera centro de alertas no dashboard; WhatsApp completo fica como P1/P2.
- Motivo: WhatsApp exige conta Meta Business, templates aprovados, custos e calibracao de ruido.
- Consequencia: eventos de alerta devem nascer no backend, mesmo que o primeiro canal seja apenas dashboard.

ADR-005: SQL como blueprint, migrations via Alembic

- Decisao: SQL em documentos e anexos serve como blueprint, nao como migration final.
- Motivo: migrations precisam ser incrementais, testaveis e alinhadas ao ORM.
- Consequencia: nenhuma tabela entra sem migration Alembic e teste minimo de criacao.

### Backend

- FastAPI.
- SQLAlchemy 2.0 async.
- Alembic.
- PostgreSQL.
- Estrutura modular por dominio.

Modulos iniciais:

- auth
- tenants
- users
- vehicles
- drivers
- files
- checklists
- fuel
- trips
- alerts
- sync
- audit

### Frontend Gestor

- Next.js.
- TypeScript.
- Tailwind.
- shadcn/ui.
- TanStack Query.
- Dashboard responsivo.

### App Motorista

- PWA React/Vite.
- IndexedDB com Dexie.js.
- Camera API.
- Geolocation API.
- Service worker.
- Fila local de sincronizacao.

### Dados

- PostgreSQL como fonte de verdade.
- Cloudflare R2 para ficheiros.
- Redis apenas quando houver necessidade real de filas/rate limit/cache.
- Se Redis nao entrar no MVP, refresh tokens e idempotencia devem usar tabelas PostgreSQL.

## 6. Modelo de Dados Minimo do MVP

Tabelas indispensaveis:

- tenants
- users
- roles/permissions ou role simples em users
- drivers
- vehicles
- files
- checklist_templates
- checklists
- fuel_logs
- trips
- trip_stops
- alerts
- audit_logs
- idempotency_keys
- sync_events ou sync_receipts
- refresh_tokens, caso Redis nao seja usado no MVP

Regras:

- Todas com tenant_id quando forem dados do cliente.
- Nunca apagar fisicamente dados operacionais criticos.
- Usar soft delete ou status.
- Usar indexes por tenant_id e entidade principal.
- Uploads devem guardar hash, mime_type, size_bytes e storage_key.
- O modelo `users` e `drivers` deve ser decidido explicitamente:
  - opcao inicial recomendada: dashboard users em `users`; motoristas em `drivers` com credencial/app token proprio.
  - se motorista precisar login completo, criar relacao `drivers.user_id`.
- `users.role` deve cobrir apenas roles do dashboard, salvo decisao contraria.
- `driver` como role so deve existir se o motorista autenticar como user.

## 7. Regras de Negocio Criticas

### Viaturas

- Matricula unica por tenant.
- Viatura em manutencao nao inicia viagem.
- Viatura sem checklist valido pode ser bloqueada por configuracao.
- Documentos vencidos geram alerta.

### Checklists

- Item bloqueante falhado impede aprovacao automatica.
- Foto obrigatoria deve ter upload associado.
- Checklist submetido nao deve ser editado livremente.
- Correccao deve gerar novo evento ou auditoria.

### Combustivel

- Km no abastecimento nao pode ser menor que ultimo km conhecido.
- Litros e custo devem ser positivos.
- Recibo pode ser obrigatorio por tenant.
- Consumo acima do limite gera alerta.

### Viagens

- Uma viatura nao pode ter duas viagens activas.
- Um motorista nao pode ter duas viagens activas.
- Fecho exige km final.
- Custos de viagem devem ser ligados a viagem.
- Viagens de carga podem exigir documento do cliente chamado Autorizacao de Carregamento ou Load Permit.
- Load Permit deve identificar cliente, distrito/local autorizado, origem/destino, validade e ficheiro/documento associado.
- Cada viagem de ida ou volta pode ter Load Permit proprio.
- A viagem deve registar estado de carga por trecho: `loaded_out_empty_return`, `empty_out_loaded_return`, `loaded_out_loaded_return`, `empty_out_empty_return` ou equivalente operacional.
- Para produtos manufaturados, o transportador pode precisar emitir Manifesto de Carga.
- Manifesto de Carga deve ficar ligado a viagem, carga, cliente/destinatario e documentos de suporte.
- Guia de transporte, Load Permit e outros documentos de carga compoem o pacote documental da viagem.
- Ao descarregar mercadoria, o motorista deve anexar documento de descarga/entrega.
- Documento de descarga valida que o transporte foi efectivamente concluido e pode ser cobrado.
- Para contratos, a cobranca mensal deve ser gerada a partir das viagens descarregadas no periodo.
- Se a carga saiu num mes e descarregou no mes seguinte, a cobranca pertence ao mes da descarga.
- Cada viagem/trecho deve ter estado de cobranca: `not_billable`, `pending_delivery_proof`, `billable`, `billed`, `billing_disputed`.
- O sistema deve indicar o que ja foi cobrado e o que falta cobrar por cliente/contrato.
- Custos de transporte podem variar por contrato, rota, tipo de carga, estado carregado/vazio, espera, portagens, barcacas, escolta, manuseamento e despesas de motorista.

### Offline Sync

- Toda operacao local deve ter idempotency_key.
- O servidor deve aceitar repeticao segura.
- Falha de sync nao deve apagar dados locais.
- Depois de sucesso, guardar recibo de sincronizacao.
- O servidor deve guardar `idempotency_key`, `tenant_id`, `driver_id`, `device_id`, `operation`, `entity_type`, `entity_id` e resposta final.
- Operacoes repetidas com a mesma `idempotency_key` devem devolver o mesmo resultado, nao criar duplicados.
- O endpoint base recomendado e `POST /api/v1/sync/batch`.
- A resposta deve incluir mapeamento `localId -> serverId` para actualizar IndexedDB.
- Fotos devem sincronizar antes das entidades que dependem delas.
- Estados locais minimos: `local_only`, `syncing`, `synced`, `retrying`, `conflict`, `failed`.
- Repeticoes devem usar backoff exponencial com limite de tentativas.

### GPS, Tempo e Evidencia

- GPS e capturado no dispositivo, nao gerado pelo servidor.
- Guardar `client_captured_at`, `server_received_at`, `gps_lat`, `gps_lng`, `gps_accuracy_m` e `gps_source` quando disponivel.
- Timestamp do servidor e a referencia de auditoria.
- Timestamp do cliente ajuda a reconstruir operacoes offline.
- Fotos devem guardar hash SHA-256 para detectar troca ou corrupcao.

### Resolucao de Conflitos

- `last-write-wins` so e aceitavel para dados criados e editados apenas pelo motorista antes de sincronizar.
- Conflitos financeiros exigem revisao manual.
- Abastecimento ja verificado pelo gestor nao deve ser sobrescrito por sync tardio.
- Viagem fechada nao deve ser reaberta automaticamente por evento offline atrasado.
- Checklist submetido nao deve ser alterado silenciosamente; correcao gera novo evento/auditoria.
- Estado `conflict` deve aparecer no dashboard do gestor.

## 8. API e Sync do MVP

### Endpoints Base

Auth:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

Tenants e users:

- `GET /api/v1/tenants/me`
- `GET /api/v1/users`
- `POST /api/v1/users`
- `PATCH /api/v1/users/{id}`

Viaturas:

- `GET /api/v1/vehicles`
- `POST /api/v1/vehicles`
- `GET /api/v1/vehicles/{id}`
- `PATCH /api/v1/vehicles/{id}`
- `GET /api/v1/vehicles/{id}/qr-code`

Motoristas:

- `GET /api/v1/drivers`
- `POST /api/v1/drivers`
- `GET /api/v1/drivers/{id}`
- `PATCH /api/v1/drivers/{id}`

Checklists:

- `GET /api/v1/checklist-templates`
- `POST /api/v1/checklist-templates`
- `GET /api/v1/checklists`
- `POST /api/v1/checklists`
- `PATCH /api/v1/checklists/{id}`
- `POST /api/v1/checklists/{id}/complete`

Combustivel:

- `GET /api/v1/fuel`
- `POST /api/v1/fuel`
- `GET /api/v1/fuel/stats`
- `GET /api/v1/fuel/anomalies`
- `PATCH /api/v1/fuel/{id}/verify`

Viagens:

- `GET /api/v1/trips`
- `POST /api/v1/trips`
- `POST /api/v1/trips/{id}/start`
- `POST /api/v1/trips/{id}/stops`
- `POST /api/v1/trips/{id}/load-permits`
- `POST /api/v1/trips/{id}/cargo-manifest`
- `POST /api/v1/trips/{id}/complete`

Ficheiros:

- `POST /api/v1/files/presign`
- `POST /api/v1/files/confirm`
- `GET /api/v1/files/{id}`

Sync:

- `POST /api/v1/sync/batch`
- `GET /api/v1/sync/bootstrap`

Operacao:

- `GET /health`
- `GET /version`

### IndexedDB Minimo

Stores locais recomendadas:

- `driverProfile`
- `vehicles`
- `checklistTemplates`
- `pendingChecklists`
- `checklistResponses`
- `activeTrip`
- `tripStops`
- `loadPermits`
- `cargoManifests`
- `tripCosts`
- `pendingFuelLogs`
- `photoQueue`
- `syncQueue`
- `destinations`

### Ordem de Sync

1. Guardar operacao localmente.
2. Gerar `idempotency_key`.
3. Guardar fotos em `photoQueue`.
4. Quando online, comprimir fotos e fazer upload.
5. Confirmar ficheiros no backend.
6. Enviar operacoes em `syncQueue`.
7. Receber `serverId`.
8. Actualizar IndexedDB.
9. Marcar estado como `synced`.

### Politica de Fotos

- Redimensionar para maximo 1920px no maior lado.
- JPEG qualidade aproximada 80%.
- Manter original local ate confirmacao do servidor.
- Upload maximo recomendado: 3 fotos em paralelo.
- Guardar `sha256_hash`, `mime_type`, `size_bytes`, `storage_key`.

## 9. Roadmap de Execucao

### Fase 0 - Fundacao Tecnica (Semana 1)

Entregaveis:

- Repositorio organizado.
- Backend FastAPI iniciado.
- Frontend gestor iniciado.
- PWA motorista iniciado.
- Configuracao de ambientes: dev, staging, prod.
- Docker local se necessario.
- Alembic configurado.
- CI inicial com lint e testes.

Decisoes a fechar:

- Hosting inicial.
- Provider de PostgreSQL.
- Estrategia de storage.
- Formato de IDs e convencoes.

### Fase 1 - Identidade, Tenants e Viaturas (Semanas 2-3)

Entregaveis:

- Login.
- Users e roles basicos.
- Tenant resolution.
- CRUD de viaturas.
- Upload de foto/documento.
- QR code por viatura.
- Audit logs basicos.

Criterio de aceite:

- Admin ve apenas dados do seu tenant.
- Matricula duplicada no mesmo tenant falha.
- Foto/documento fica associado a viatura.

### Fase 2 - Motoristas e Checklists (Semanas 3-5)

Entregaveis:

- CRUD de motoristas.
- Templates de checklist.
- Execucao de checklist pre-partida e chegada.
- Fotos por item.
- GPS quando disponivel.
- Estado: em progresso, concluido, falhou, pendente sync.

Criterio de aceite:

- Motorista completa checklist no telemovel.
- Checklist funciona sem rede.
- Ao voltar internet, sincroniza sem duplicar.

### Fase 3 - Combustivel e Viagens (Semanas 5-7)

Entregaveis:

- Registo de abastecimento.
- Foto do recibo e odometro.
- Calculo de consumo.
- Abertura e fecho de viagem.
- Paragens simples.
- Custos basicos por viagem.

Criterio de aceite:

- Sistema calcula custo/km basico.
- Consumo anormal gera alerta interno.
- Viagem nao fecha sem km final.

### Fase 4 - Dashboard, Alertas e Piloto (Semana 8)

Entregaveis:

- Dashboard operacional.
- Centro de alertas.
- Relatorio mensal simples por viatura.
- Seeds/demo data.
- Guia de onboarding de cliente piloto.
- Checklist de suporte.

Criterio de aceite:

- Gestor consegue operar rotina diaria.
- Motorista consegue usar PWA com pouca instrucao.
- Dados reais entram e aparecem no dashboard.

## 10. Matriz de Prioridade

P0 - indispensavel:

- Auth/multi-tenant.
- ADRs registadas no repositorio.
- Viaturas.
- Motoristas.
- Checklists.
- Offline sync.
- Idempotencia.
- Combustivel.
- Viagens.
- Upload de fotos.
- Alertas internos.
- Auditoria basica.

P1 - importante:

- Relatorio mensal.
- QR code.
- Dashboard financeiro simples.
- Exportacao PDF/Excel.
- Presigned uploads robustos.
- Permissoes granulares por modulo.

P2 - depois do piloto:

- WhatsApp completo.
- Manutencao.
- Acessorios.
- Score de motorista.
- Pagamentos.

P3 - futuro:

- Marketplace.
- Seguradoras.
- Financiadores.
- IA preditiva.
- Integracoes externas profundas.

## 11. Definition of Done

Uma funcionalidade so esta pronta quando:

- Tem regra de negocio implementada no backend.
- Tem validacao de permissao e tenant.
- Tem teste unitario ou de integracao proporcional ao risco.
- Tem estado de loading, vazio e erro no frontend.
- Tem logs em operacoes criticas.
- Tem migration Alembic.
- Tem tratamento de erro legivel para utilizador.
- Tem auditoria quando altera dado sensivel.
- Foi testada em ecras pequenos.
- Foi testada com rede lenta ou offline quando aplicavel.
- Operacoes offline usam idempotency_key quando aplicavel.
- Se envolve fotos, valida hash, tamanho, mime_type e associacao a entidade.
- Se envolve dados financeiros, define regra de conflito e revisao.

## 12. Riscos de Falha

1. Escopo inchado
   - Mitigacao: MVP fechado em 4 fluxos: viaturas, checklists, combustivel, viagens.

2. Offline mal implementado
   - Mitigacao: testar sync desde o primeiro checklist, nao no fim.

3. Interface complexa para motorista
   - Mitigacao: prototipar com utilizador real antes de completar dashboard bonito.

4. Dados financeiros inconsistentes
   - Mitigacao: normalizar combustivel, viagens e custos desde cedo.

5. Falta de confianca nos dados
   - Mitigacao: fotos, GPS, timestamps e auditoria.

6. Premissas legais erradas
   - Mitigacao: validar privacidade, INATTER, pagamentos e retencao com fonte juridica local antes de vender como conformidade oficial.

7. WhatsApp caro ou ruidoso
   - Mitigacao: comecar com alertas internos e activar WhatsApp apenas para eventos criticos.

## 13. Validacoes Externas Pendentes

Antes de documento comercial final:

- Confirmar estado actual da lei de proteccao de dados em Mocambique.
- Confirmar requisitos INATTER relevantes para transporte de carga/passageiros.
- Confirmar custos e requisitos da WhatsApp Cloud API para Mocambique.
- Confirmar disponibilidade real de M-Pesa/e-Mola APIs para integracao comercial.
- Confirmar estatisticas de uso de WhatsApp com fonte confiavel.
- Validar precos com pelo menos 5 potenciais clientes.

## 14. Primeira Semana - Checklist de Arranque

- Definir nome dos repositorios.
- Criar pasta `/docs/adr` e registar ADR-001 a ADR-005.
- Criar estrutura backend.
- Criar estrutura frontend gestor.
- Criar estrutura PWA motorista.
- Definir variaveis de ambiente.
- Criar modelos iniciais: tenants, users, vehicles, drivers.
- Criar modelo `idempotency_keys`.
- Decidir formalmente `users` vs `drivers`.
- Criar primeira migration.
- Criar endpoint healthcheck.
- Criar endpoint version.
- Criar login basico.
- Criar seed de tenant demo.
- Criar layout inicial do dashboard.
- Criar tela inicial do motorista.
- Criar prototipo minimo de IndexedDB com `syncQueue` e `photoQueue`.

## 15. Decisao Central

O ROTAS nao deve ser avaliado pela quantidade de funcionalidades no primeiro lancamento.

Deve ser avaliado por:

- Confianca dos dados.
- Simplicidade para motorista.
- Clareza para gestor.
- Funcionamento offline.
- Capacidade de provar custo, historico e responsabilidade.

Esta e a base. O resto escala depois.
