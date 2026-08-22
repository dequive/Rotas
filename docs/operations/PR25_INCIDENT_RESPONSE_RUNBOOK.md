# PR-25 — Runbook de On-call, Suporte e Resposta a Incidentes

## Estatuto e limites

Este runbook implementa a baseline operacional do PR-25. A política canónica é
`infra/operations/INCIDENT_RESPONSE_POLICY.json`.

Um tabletop local valida o encadeamento dos controlos, mas não prova entrega
real de páginas, escalonamento humano, recuperação regional, tempos de resposta
ou operação num release candidate. PR-25 só pode ser concluído após um game day
em staging production-like, com participantes e canais reais.

## Fonte de verdade do on-call

A escala primária/secundária, contactos e credenciais vivem num diretório
externo aprovado. Nomes, telefones, emails e tokens não são versionados.

Antes de cada período on-call, SRE confirma:

1. primário, secundário e Incident Commander disponíveis;
2. acesso a staging/produção, Grafana, Alertmanager, PostgreSQL, Redis,
   Governance, R2 e repositório DR;
3. canal de paging e canal de incidente testados;
4. contactos de Segurança/Privacidade, PO e liderança acessíveis;
5. handoff com incidentes e riscos abertos.

## Declaração e severidade

- `SEV1`: indisponibilidade total, violação confirmada de isolamento, perda
  material de dados ou falha operacional safety-critical;
- `SEV2`: degradação grave, jornada crítica bloqueada ou suspeita de problema
  de segurança/integridade;
- `SEV3`: impacto limitado, workaround disponível e sem impacto conhecido em
  isolamento, segurança ou contabilidade;
- `SEV4`: pedido/defeito de baixo risco para planeamento normal.

Na dúvida entre duas severidades, declarar a mais alta até haver evidência.
Uma suspeita de isolamento entre tenants nunca começa abaixo de `SEV2`.

## Fluxo obrigatório

1. **Declarar**: criar ID, timestamp UTC, severidade, sistema, sintoma e
   Incident Commander.
2. **Triar**: separar facto, hipótese e desconhecido; delimitar tenants e
   jornadas potencialmente afetados sem publicar identificadores.
3. **Conter**: congelar promoção, revogar acesso/flag/integração ou executar
   rollback/forward-fix seguro. Nunca editar movimentos, faturas, outbox ou
   auditoria diretamente.
4. **Recuperar**: aplicar o runbook técnico adequado e registar comandos,
   artefactos, SHA/digest e aprovações.
5. **Validar**: um segundo operador comprova health, autenticação, RLS,
   jornadas afetadas, contabilidade/outbox e ausência de regressão.
6. **Monitorizar**: manter janela explícita sem recorrência.
7. **Resolver**: comunicar recuperação e impacto conhecido, preservando
   incertezas.
8. **Rever**: post-incident review, ações com owner/data e verificação de
   conclusão. A revisão não fecha com ações abertas.

## Papéis

- Incident Commander: coordena, decide severidade e mantém foco;
- Operations Lead: executa mitigação e recuperação;
- Communications Lead: mantém cadência interna, status e clientes afetados;
- Scribe: preserva timeline, decisões, comandos e evidência;
- Security/Privacy Lead: obrigatório em SEV1/SEV2 de segurança ou dados;
- Business Owner: avalia impacto operacional e aprova comunicação comercial.

Uma pessoa pode acumular papéis apenas se o exercício comprovar capacidade e
existir substituto. O executor da recuperação não pode ser o único validador.

## Comunicação multi-tenant

- status público não inclui `tenant_id`, nomes de clientes, utilizadores,
  documentos, matrículas ou payloads;
- comunicação dirigida é isolada por tenant e contém apenas o impacto desse
  tenant;
- nunca confirmar ausência de exposição antes de terminar a investigação;
- suspeita de dados pessoais aciona Segurança/Privacidade e validação jurídica;
- o Operador SaaS comunica com o tenant; o tenant decide a comunicação com os
  seus próprios clientes, salvo obrigação legal/contratual diferente.

## Rotas técnicas

- disponibilidade, 5xx, latência e DLQ:
  `docs/observability/PR20_OBSERVABILITY_RUNBOOK.md`;
- backup, restore e perda de dados:
  `docs/DR_BACKUP_RESTORE_RUNBOOK.md`;
- carga/rede degradada:
  `docs/PERFORMANCE_AND_RESILIENCE_RUNBOOK.md`;
- isolamento e privacidade:
  `docs/security/ROTAS_THREAT_AND_PRIVACY_MODEL.md`;
- promoção/rollback:
  `docs/STAGING_DEPLOYMENT_RUNBOOK.md`.

## Game day obrigatório para G4

O exercício no mesmo RC deve cobrir os cinco cenários canónicos da política,
incluindo paging real, participação de SRE/PO/Segurança/QA, handoff
primário-secundário, comunicação simulada por tenant e validação independente.

Evidência mínima:

- SHA e digests do RC, ambiente e janela;
- participantes e papéis confirmados fora do repositório público;
- tempos de alerta, ack, declaração, contenção, recuperação e comunicação;
- mensagens entregues pelos canais reais;
- comandos, dashboards, logs/traces e decisões;
- RPO/RTO medidos no cenário DR;
- regressões de RLS, jornadas, contabilidade e outbox;
- ações, owners, prazos e sign-off de SRE + PO + QA.

O tabletop local pode ser executado com:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.incident_game_day `
  --repo-root .. `
  --release-ref working-tree `
  --confirm-local-tabletop PR25-LOCAL-TABLETOP `
  --report-path ..\docs\evidence\PR25_LOCAL_TABLETOP_<data>.json
```

O relatório resultante deve permanecer `local_control_plane_only`; não é
evidência suficiente para G4.
