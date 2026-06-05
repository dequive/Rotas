# Features Research
_Last updated: 2026-06-04_

## Summary

ROTAS is building fleet management SaaS for Mozambican logistics operators with an offline-first driver PWA. The core architecture (offline sync, trip lifecycle, fuel management, workshop, compliance blocking, multi-tenancy) covers the hardest-to-build parts of the domain. What is largely absent is the **reporting/analytics layer**, **automated alerting infrastructure**, **preventive maintenance scheduling**, and **role differentiation** that turn a data-collection tool into an operational management platform. The Africa-specific market context strongly validates the offline-first and compliance-heavy approach, and does not require GPS streaming or advanced AI/telematics hardware for MVP. The biggest gap versus table stakes is a manager-facing dashboard with actionable KPIs and a document-expiry alert system.

---

## Table Stakes (must have or users leave)

### Fleet & Vehicle Management
- **Vehicle registry** with registration plate, make/model, year, VIN — ROTAS has this
- **Document expiry tracking** for registration, insurance, road tax, technical inspection (INATTER) — ROTAS has compliance_policy JSONB but automated email/push alerts on approaching expiry are absent
- **Odometer tracking** tied to service intervals — ROTAS has odometer but PM scheduling triggers are absent
- **Vehicle status** (available / on trip / in workshop / blocked) — ROTAS has trip + workshop blocking; needs explicit "status board" view

### Driver Management
- **Driver document compliance** (license, medical certificate, INATTER authorisation) with expiry dates — ROTAS has this + departure blocking
- **Driver availability** (on trip / off duty / suspended) — ROTAS has this
- **Role-based access**: admin, fleet manager, dispatcher, driver — ROTAS has manager vs driver but lacks dispatcher role and granular permissions

### Trip & Dispatch Operations
- **Trip creation and assignment** to driver + vehicle — ROTAS has this
- **Delivery proof / POD capture** (photo, signature, timestamp) — ROTAS has this
- **Trip status lifecycle** (planned → dispatched → in progress → completed) — ROTAS has this
- **Cargo manifest / load permit** attached to trip — ROTAS has this
- **Stop logging** with timestamps and costs — ROTAS has this
- **Offline operation**: driver completes full trip without connectivity — ROTAS has Dexie.js sync queue but Service Worker is missing (PWA-01)

### Fuel Management
- **Fuel fill recording** per vehicle with odometer, litres, cost — ROTAS has this
- **Fuel cost reporting** per vehicle, per period — ROTAS has weighted average cost; exportable reporting is weak
- **Internal tank management** with stock reconciliation — ROTAS has this
- **Fuel variance alerting** (fills out of normal range) — ROTAS has reconciliation concept; automated alerts absent

### Maintenance & Workshop
- **Workshop order management** with status workflow — ROTAS has this
- **Parts inventory** with consumption against orders — ROTAS has this
- **Preventive maintenance scheduling** triggered by odometer or calendar interval — ROTAS has workshop but no PM schedule / trigger engine
- **Maintenance cost per vehicle** reporting — absent

### Reporting & Analytics (MAJOR GAP)
- **Cost-per-km/trip** for each vehicle — absent; data exists but not surfaced
- **Fleet utilisation rate** (active hours / available hours) — absent
- **Fuel consumption trend** per vehicle — absent
- **Maintenance cost trend** — absent
- **Driver trip summary** (trips completed, km driven, fuel used) — absent
- **Exportable reports** (PDF + XLSX) for management and clients — ROTAS has BILL-01 / BILL-02 pending for invoices only

### Billing & Invoicing
- **Monthly invoice generation** grouped by delivery proof — ROTAS has this logic
- **PDF invoice export** — pending (BILL-01)
- **XLSX export** — pending (BILL-02)
- **Negative margin waiver workflow** — pending (BILL-03)

### Automated Alerts & Notifications (SIGNIFICANT GAP)
- **Document expiry reminders** (30/15/7 days before) for vehicles and drivers — absent
- **Overdue maintenance alerts** — absent
- **Departure block notifications** (why a vehicle/driver is blocked) — ROTAS blocks departure but notification path unclear
- **Delivery exception alerts** to manager — partially via Control Tower

### Authentication & Security
- **JWT with token refresh** — pending (AUTH-01, AUTH-02)
- **Rate limiting on auth endpoints** — pending (SEC-03)
- **Secure session cookies** in production — pending (SEC-04)

---

## Differentiators (competitive advantage)

### Offline-First PWA with Full Trip Lifecycle
Most Africa-market competitors (Cartrack, MiX by Powerfleet, Ctrack) require hardware telematics devices and GSM connectivity. ROTAS's ability to complete an entire trip workflow — departure checklist, fuel fill, stops, delivery proof — on a low-end Android PWA with zero connectivity is genuinely differentiated for Mozambique's secondary routes. **Confidence: HIGH** — confirmed by Cartrack/MiX product pages and Africa market pain point research.

### Compliance-Gated Operations
Blocking departure when driver license or INATTER certificate is expired (enforced server-side + IndexedDB locally) is operationally safer than alert-only systems. This is rare in SME-focused tools. **Confidence: MEDIUM** — competitor feature comparison limited to public marketing pages.

### Multi-Tenant SaaS for Mozambican Market
No identified competitor offers a purpose-built SaaS for Mozambican transportadoras with Portuguese-language UI, local compliance rules, and meticais (MZN) as the primary currency. Regional leaders (Cartrack, Tracker) target South Africa with hardware-centric models. **Confidence: MEDIUM** — Mozambique-specific product research returned no direct competitors; MEDIUM because absence of evidence is not evidence of absence.

### Driver Scorecard (future differentiator, not yet built)
Driver performance scoring (speeding events from GPS payloads, harsh braking if OBD available, fuel efficiency per driver) enables cost reduction through targeted coaching. Africa fleet managers cite this as high-value. Would require surface-level UI on top of existing sync data. **Confidence: HIGH** — validated by Geotab, MiX, EcoTrack, and Africa fleet pain point sources.

### Weighted Average Fuel Cost (WACC)
Accurate fuel cost attribution using WACC across internal tanks is uncommon in SME tools and directly supports the billing accuracy requirement. **Confidence: MEDIUM** — rare to find this in SME fleet tools based on research.

### Cross-Border Documentation Support (future)
Mozambique operators run SADC cross-border routes (Maputo–Johannesburg, Beira–Harare corridors). Supporting Guia de Transporte, SADC certificate of origin, and cross-border permit tracking in-app would be unique for SME operators who currently manage this on paper. **Confidence: MEDIUM** — documentation requirements confirmed by CBRTA handbook and SADC research; no current competitor identified supporting this digitally for SME operators.

---

## Anti-Features (deliberately NOT build for MVP)

| Anti-Feature | Reasoning | What to do instead |
|---|---|---|
| Real-time GPS streaming / live tracking | Requires always-on device data connection, hardware OBD dongle, or mobile data plan per vehicle. Android low-end devices in Mozambique cannot sustain streaming. High infra cost. | Store GPS coordinate in sync payload; show last-known position on manager dashboard |
| AI dashcam / video telematics | Hardware cost $300–$500 per vehicle, requires 4G SIM, specialist installation. Not viable for SME fleet in Mozambique. | Driver scorecard from trip data and fuel fills is sufficient for MVP coaching |
| Route optimisation engine | Requires reliable map data for Mozambique (poor OSM coverage outside Maputo), complex algorithmic work, adds no value until basic reporting exists | Log actual routes; optimisation is a Phase N feature |
| Native iOS/Android app | PWA with Service Worker covers offline use case; App Store distribution adds operational complexity for a B2B SaaS | Complete Workbox Service Worker (PWA-01 to PWA-03) |
| ERP / accounting system integration (SAP, Sage, QuickBooks) | Zero demand signal from Mozambican SME operators who are pre-ERP; adds integration maintenance burden | XLSX + PDF export is sufficient bridge to any accounting tool |
| Fuel card integrations | No dominant fuel card network in Mozambique (unlike WEX / Comdata in USA); manual entry is the norm | Manual fuel fill recording with photo receipt is sufficient |
| Marketplace / load board | B2C feature; out of scope for B2B fleet management SaaS | Out of scope |
| Driver payroll / HR module | Overlaps with dedicated HR software; different buyer in same organisation | Driver allowance/diária per trip is sufficient financial tracking |
| ELD (Electronic Logging Device) compliance | FMCSA HOS rules are USA-specific; Mozambique has no equivalent electronic hours-of-service mandate | Driver trip start/end timestamps satisfy local record-keeping |

---

## Africa / Emerging Market Specifics

### Connectivity Constraints
- GSM coverage is unreliable outside Maputo, Beira, Nampula. Routes to Zimbabwe (Beira Corridor), South Africa (Maputo Corridor), and Malawi frequently lose signal for hours.
- Low-end Android devices (< $100) dominate driver handsets. Heavy JavaScript bundles, large image uploads, and WebSocket connections are unreliable.
- **Implication for ROTAS:** Service Worker caching of the PWA shell and API responses is not optional — it is the core product promise. Delta sync over batch is important to minimise data costs (users pay per MB).

### Cash and Informal Economy
- Most fleet operating costs (fuel, tolls, driver allowances, stop costs) are cash-based. Manual entry is not a weakness — it is the correct model for this market.
- Expense reconciliation is done manually at trip close; automated bank-feed reconciliation has no applicability here.
- **Implication for ROTAS:** The trip cost capture model (manual entry per stop/fuel fill) is correct. Automated reconciliation against fuel card transactions would be wasted effort.

### Driver Digital Literacy
- Many Mozambican truck drivers have basic smartphone literacy. WhatsApp and M-Pesa are widely used, but complex form UIs cause friction.
- South African fleet operators confirm WhatsApp groups + spreadsheets are still the baseline for many fleets.
- **Implication for ROTAS:** Driver PWA must minimise UI complexity. Large tap targets, Portuguese labels, progress indicators. Single primary action per screen. Avoid optional fields.

### Compliance Landscape (Mozambique)
- **INATTER** (Instituto Nacional de Transportes Terrestres): regulates vehicle technical inspection, driver licensing, and operating permits. Annual vehicle inspection required. Driver authorisation cards distinct from license.
- **Licença de Operador**: transport operating licence required for commercial freight operators.
- **Seguros**: mandatory third-party insurance (Seguro de Responsabilidade Civil). Insurance expiry is a common roadside stop trigger.
- **Guia de Transporte**: cargo transport document required in-vehicle for all commercial freight. Equivalent to a consignment note / bill of lading for road transport.
- **Livrete do Veículo**: vehicle registration book. Must be in-vehicle at all times.
- **Cross-border**: Cross-Border Road Transport Permit (CBRTA), SADC Certificate of Origin, carnet de passage for temporary import. Separate documents per corridor.
- **Tax context**: Mozambique has VAT (IVA at 17%). Transport services may be VAT-exempt for intra-country freight, but cross-border billing requires correct tax treatment.
- **Implication for ROTAS:** INATTER inspection date, insurance expiry, Licença de Operador expiry, and individual driver INATTER authorisation are the four critical compliance dates to track and alert on. The existing `compliance_policy` JSONB is the right abstraction.

### Payment and Billing
- B2B payments are typically bank transfer or cheque. Mobile money (M-Pesa, e-Mola) used for individual payments but not large freight invoices.
- Invoice generation in MZN with correct UTF-8 character support for names with diacritics is table stakes for any Mozambican business tool.
- **Implication for ROTAS:** BILL-01 (PDF export) and BILL-02 (XLSX export) are blockers for production use. This is not a differentiator — it is a baseline requirement.

### Hardware Context
- Telematics hardware (GPS trackers, OBD dongles) exists in the Mozambican market (Cartrack has Mozambique presence) but targets larger corporate fleets. SME operators cannot afford $15–$30/month/vehicle hardware fees on top of software.
- **Implication for ROTAS:** Software-only, no hardware dependency is the right positioning for SME. GPS coordinates from the driver's phone (captured at trip sync events) are sufficient.

---

## Gaps in Current ROTAS Feature Set

### Critical Gaps (block production readiness)

| Gap | Description | Priority |
|---|---|---|
| Service Worker absent | The offline-first promise is undeliverable without PWA-01 to PWA-03. Dexie.js sync queue works but the app cannot load offline or queue sync in background. | Critical |
| No preventive maintenance scheduler | Odometer data exists but there is no trigger engine to generate service reminders at N km intervals or M months. Workshop orders are reactive only. | High |
| No reporting / analytics layer | Cost-per-km, utilisation rate, fuel trend, driver trip summary — none surfaced to manager. All raw data exists in PostgreSQL but no aggregation queries or dashboard charts. | High |
| Document expiry alerts absent | Compliance policy blocks departure but does not proactively notify manager when expiry is approaching. Operators will be surprised by blocked vehicles. | High |
| Dispatcher role missing | Trips are created by manager. No intermediate dispatcher role who can create/assign trips without full admin access. Blocks multi-person operations teams. | Medium |

### Moderate Gaps (important but not launch-blockers)

| Gap | Description | Priority |
|---|---|---|
| No PM schedule → work order automation | When a PM interval is reached, system should auto-create a maintenance work order and alert the manager. | Medium |
| No cost-per-vehicle P&L view | Revenue (billing) and costs (fuel + maintenance + allowances per vehicle) are captured separately; no unified per-vehicle profitability view. | Medium |
| No driver scorecard | Trip history, km driven, fuel consumption per driver. Data exists in sync payloads; UI and aggregation absent. | Medium |
| Fuel consumption per vehicle trend | Fuel fills are recorded but no time-series trend view per vehicle to spot degrading efficiency. | Medium |
| No bulk document upload / management | Vehicle and driver compliance documents referenced by expiry date but document files (scans of certificates) not systematically stored per document type. | Low–Medium |
| No notifications infrastructure | Email and/or push notification channel absent. Required for expiry alerts, delivery confirmations, exception escalations. | Medium |

### Acceptable Gaps for MVP (out of scope)

| Gap | Why acceptable |
|---|---|
| Real-time GPS tracking | No hardware; GPS in sync payload is sufficient for trip reconstruction |
| Fuel card integration | No fuel card network in Mozambique |
| ERP integration | SME operators pre-ERP; XLSX export sufficient |
| Driver scoring on video telematics | Requires dashcam hardware |
| Route optimisation | Map data quality insufficient for Mozambique outside Maputo |

---

## Gaps / Unknowns

1. **Conflict resolution strategy in offline sync**: Research confirms ROTAS's idempotency-key approach is sound for append-heavy data (fuel fills, checklist answers, delivery proofs). The specific conflict handling for `update` events (AUTH-04 is still pending) is unresolved. Last-write-wins is adequate for most fleet data; only inventory quantities (parts) and odometer readings need merge logic. **Needs engineering decision.**

2. **Delta sync vs full sync**: Current `POST /api/v1/sync/batch` sends full entity payloads. For large fleets with many trips, bandwidth cost on Mozambican mobile data plans (expensive per MB) will matter. Delta sync sending only changed fields since last sync sequence number is the production pattern (confirmed by PowerSync, ElectricSQL research). **Needs architecture decision for v2.**

3. **Notification delivery channel**: Email is unreliable for Mozambican operators (low corporate email adoption); WhatsApp Business API is the most-used business communication channel. SMS as fallback. Push notifications via Service Worker are viable for manager dashboard (web). The right channel mix is unknown without customer validation. **Needs market validation.**

4. **Fiscal document requirements**: Mozambique has specific e-fatura (electronic invoice) regulations under the AT (Autoridade Tributária). Whether commercial freight invoices between companies require AT-registered invoice numbers is unclear from research. **Needs legal validation before billing feature ships to production.**

5. **Cross-border permit tracking demand**: Research confirms cross-border is a real workflow for Mozambican transportadoras (Maputo Corridor, Beira Corridor). Whether SME operators would pay for this in-app vs managing on paper is unvalidated. **Needs customer interview.**

6. **Competing SaaS in Mozambique**: No direct software competitor identified for Portuguese-language, Mozambique-native fleet management SaaS targeting SME operators. Cartrack has hardware-dependent tracking in Mozambique but their SME software is South Africa-centric. Absence of identified competitors increases market opportunity but also increases risk that the market is pre-SaaS (operators not ready to pay for software). **Needs sales validation.**
