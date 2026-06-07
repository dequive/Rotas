# WhatsApp Templates — ROTAS

Templates para submeter no Meta Business Manager.
Tipo: **UTILITY** | Idioma: **pt_PT** | Categoria: **TRANSACTIONAL**

---

## 1. `trip_dispatched`
**Quando enviar:** Quando um gestor atribui uma viagem a um motorista.

```
Olá {{1}},

Foi-lhe atribuída uma nova viagem:
• Destino: {{2}}
• Data de partida: {{3}}
• Veículo: {{4}}

Abra a app ROTAS Motorista para ver os detalhes e confirmar a viagem.
```

Variáveis: `{{1}}` nome do motorista, `{{2}}` destino, `{{3}}` data/hora partida, `{{4}}` matrícula

---

## 2. `delivery_completed`
**Quando enviar:** Quando o motorista regista a prova de entrega na app.

```
Entrega concluída ✓

Motorista: {{1}}
Destino: {{2}}
Hora de entrega: {{3}}
Receptor: {{4}}

Aceda ao dashboard ROTAS para validar a prova de entrega.
```

Variáveis: `{{1}}` nome motorista, `{{2}}` destino, `{{3}}` hora entrega, `{{4}}` nome receptor

---

## 3. `eta_update`
**Quando enviar:** Durante a viagem, quando a ETA é actualizada.

```
Actualização de ETA — {{1}}

Veículo {{2}} está a {{3}} km do destino.
Chegada prevista: {{4}}

Acompanhe em tempo real no dashboard ROTAS.
```

Variáveis: `{{1}}` referência viagem, `{{2}}` matrícula, `{{3}}` km restantes, `{{4}}` hora chegada estimada

---

## 4. `document_expiring`
**Quando enviar:** 30, 15 e 7 dias antes do vencimento de um documento.

```
⚠️ Documento a vencer — {{1}}

O documento *{{2}}* de {{3}} vence em *{{4}} dias* ({{5}}).

Renove o documento antes da data de vencimento para evitar bloqueios operacionais.
```

Variáveis: `{{1}}` empresa/tenant, `{{2}}` tipo de documento, `{{3}}` veículo ou motorista, `{{4}}` dias restantes, `{{5}}` data vencimento

---

## 5. `settlement_approved`
**Quando enviar:** Quando o gestor aprova a liquidação de deslocação de um motorista.

```
Liquidação aprovada ✓

Olá {{1}},

A sua liquidação de deslocação para a viagem {{2}} foi aprovada.
• Valor: {{3}} MZN
• Data de aprovação: {{4}}

O valor será processado de acordo com a política da empresa.
```

Variáveis: `{{1}}` nome motorista, `{{2}}` referência viagem, `{{3}}` valor, `{{4}}` data aprovação

---

## 6. `settlement_disputed`
**Quando enviar:** Quando um motorista contesta uma liquidação no app.

```
Liquidação contestada — {{1}}

O motorista {{2}} contestou a liquidação da viagem {{3}}.
Motivo: {{4}}

Aceda ao dashboard ROTAS para rever e responder.
```

Variáveis: `{{1}}` empresa/tenant, `{{2}}` nome motorista, `{{3}}` referência viagem, `{{4}}` motivo da contestação

---

## 7. `driver_blocked`
**Quando enviar:** Quando um motorista é bloqueado por documentos em falta ou expirados.

```
Motorista bloqueado — {{1}}

O motorista {{2}} foi bloqueado por documentação em falta ou expirada:
• {{3}}

O motorista não poderá iniciar novas viagens até a situação ser regularizada.
Aceda ao dashboard ROTAS para renovar os documentos.
```

Variáveis: `{{1}}` empresa/tenant, `{{2}}` nome motorista, `{{3}}` lista de documentos em falta/expirados

---

## Como submeter no Meta Business Manager

1. Acede a [business.facebook.com](https://business.facebook.com)
2. WhatsApp → Conta WhatsApp Business → Gerir → Message Templates
3. **Criar template** para cada um dos 7 acima:
   - Nome: usar o nome exacto (ex: `trip_dispatched`)
   - Categoria: **Utility**
   - Idioma: **Português (Portugal)** — `pt_PT`
   - Corpo: copiar o texto do template
   - Variáveis: declarar cada `{{N}}`
4. Submeter para aprovação

Meta demora 1-3 dias por template. Se a conta ainda não tem verificação de negócio, pode demorar 5-14 dias adicionais.
