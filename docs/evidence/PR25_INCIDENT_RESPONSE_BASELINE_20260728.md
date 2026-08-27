# PR-25 — Baseline de On-call e Resposta a Incidentes

Data: 2026-07-28  
Estado: `in_progress`  
Âmbito da evidência: `working-tree`, tabletop local  
Efeito no gate: nenhum; G4 permanece vermelho

## Resultado

Foi criada uma baseline fail-closed para on-call, suporte, incident response e
game day. O contrato liga PR-20/observabilidade, PR-21/DR, segurança,
performance e promoção, preservando a hierarquia:

`Operador ROTAS SaaS -> tenant independente -> clientes próprios do tenant`.

A baseline não declara que pessoas foram paginadas, que um incidente real foi
resolvido ou que RPO/RTO foram cumpridos.

## Artefactos

- `infra/operations/INCIDENT_RESPONSE_POLICY.json`;
- `docs/operations/PR25_INCIDENT_RESPONSE_RUNBOOK.md`;
- `backend/scripts/validate_incident_response.py`;
- `backend/scripts/incident_game_day.py`;
- `backend/tests/test_incident_response.py`;
- `docs/evidence/PR25_LOCAL_TABLETOP_20260728.json`;
- gate bloqueante em `.github/workflows/ci.yml`.

## Contrato versionado

- quatro severidades (`SEV1` a `SEV4`) com tempos máximos;
- seis papéis com validação independente da recuperação;
- sete estados do incidente, da declaração ao fecho da revisão;
- roster e endpoint de paging obrigatoriamente externos ao repositório;
- comunicação pública sem identificadores e comunicação isolada por tenant;
- evidência, timeline, decisões, comandos, recuperação e ações obrigatórias;
- cinco cenários: backend indisponível, erro/latência, DLQ, perda/restore e
  isolamento/privacidade.

## Evidência local reproduzida

```text
Ruff: All checks passed
Pytest PR-25: 4 passed
Validador: 4 severidades, 6 papéis, 7 estados, 5 cenários
Tabletop: tabletop_passed
evidence_scope: local_control_plane_only
gate_effect: none
```

O tabletop confirmou somente que cada cenário possui sinal, severidade,
runbook e controlos esperados. O próprio relatório preserva como não provados:

- entrega real de paging;
- ack e escalonamento humanos;
- injeção de falha production-like;
- contenção e recuperação medidas;
- RPO/RTO medidos;
- operador independente e sign-off.

## Critérios ainda pendentes

PR-25 só pode passar a concluído quando:

1. PR-20 entrega alertas reais e observabilidade implantada no RC;
2. PR-21 executa PITR/restore production-like com operador independente;
3. escala primária/secundária e acessos são aprovados fora do repositório;
4. os cinco cenários são exercitados no mesmo RC;
5. mensagens chegam pelos canais reais e por escopo de tenant;
6. tempos de alerta, ack, contenção, recuperação e comunicação são medidos;
7. ações do game day têm owner, data e verificação de encerramento;
8. SRE, PO e QA assinam a evidência.

Assim, PR-25 avança de `pending` para `in_progress`, mas G4 continua vermelho e
PR-26 permanece bloqueado.
