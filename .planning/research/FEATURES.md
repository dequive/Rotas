# Features Research — ROTAS v2.0 Operational Platform
_Last updated: 2026-06-06_
_Supersedes: 2026-06-04 entry (v1 landscape only)_

---

## Summary

ROTAS v2.0 adds seven capability areas on top of a working fleet-data-collection platform. The table-stakes line for each feature is lower than it might appear because the target market (Mozambican SME transportadoras) runs informal operations today — spreadsheets and WhatsApp groups. The bar is not "match Samsara"; it is "replace the spreadsheet reliably." Every feature below has a low floor and a high ceiling. The research below defines the floor (must ship), ceiling (aspirational), and the specific Mozambique-market constraints that shape both.

**Overall confidence: MEDIUM** — no external sources available during this research session (WebSearch and WebFetch denied). All findings are derived from training data (knowledge cutoff August 2025) plus domain reasoning from the existing codebase context. Confidence is noted per-feature.

---

## Feature 1: GPS Integration (Teltonika / Coban)

**Confidence: MEDIUM-HIGH** — Teltonika protocol documentation and fleet GPS integration patterns are well-documented in training data.

### How it actually works

Teltonika devices (FMB series, TST100, etc.) and Coban/GT06-family devices operate in two distinct modes that serve different integration patterns:

**Mode A — Server push (TCP socket, proprietary codec)**
The device opens a persistent TCP connection to your server and pushes position records in a binary protocol. Teltonika uses Codec 8 / Codec 8 Extended. The server must implement a TCP socket listener that speaks this binary protocol. This is the primary/default mode for Teltonika. It is NOT an HTTP webhook — it is a raw TCP stream.

Codec 8 position record fields (minimum set):
- `timestamp` — Unix epoch in milliseconds
- `longitude`, `latitude` — float64, degrees × 10,000,000
- `altitude` — int16, meters
- `angle` — uint16, degrees from north
- `satellites` — uint8, number of satellites
- `speed` — uint16, km/h
- `priority` — event priority (0=low, 1=high, 2=panic)
- `IO elements` — variable-length set of I/O event values (ignition, odometer pulse, battery voltage, etc.)

**Mode B — HTTP/HTTPS GET or POST**
Many Coban/GT06 clones and some Teltonika devices can be configured to HTTP-poll or HTTP-POST JSON/CSV position data to a URL. This is device-configuration-dependent (set via SMS command or web portal per device). The HTTP payload is typically:
```
GET /api?imei=123456789&lat=25.123&lng=32.456&speed=60&course=180&altitude=200&ts=1717600000
```
or a JSON POST body. Field naming varies by firmware version — there is no standard.

**Mode C — MQTT (Teltonika TFT100, newer FMB devices)**
Some newer Teltonika devices support MQTT. Topic: `{imei}/telemetry`. Payload is JSON. Requires MQTT broker (Mosquitto or cloud MQTT). This is the cleanest integration but requires infrastructure.

### For ROTAS: recommended integration approach

**Practical recommendation for Mozambique context (MEDIUM confidence):**

The device hardware is already installed on trucks. The operator's existing SIM setup determines which mode is active. Before building, ROTAS must query operators about their current telematics setup:
1. Is the device sending to a Teltonika-provided server already (Teltonika FOTA / FM)?
2. Can they reconfigure to send to ROTAS's endpoint?
3. What firmware version is running?

Given these unknowns, the lowest-risk integration approach is **HTTP webhook reception**, not TCP socket server:
- Configure devices (if reconfigurable) to send HTTP POST with JSON payload to `POST /api/v1/gps/telemetry/{imei}`
- Accept whatever JSON shape the device sends, store raw payload as JSONB, normalize to `(lat, lng, speed, heading, ts, imei)` at ingest time
- Associate IMEI to vehicle via a `vehicle_gps_devices` table: `(tenant_id, vehicle_id, imei, provider)`

**Why not TCP socket server:**
- Requires separate always-on process (not a FastAPI route)
- Railway/Render do not expose raw TCP ports — requires separate infra or a proxy
- Complex binary protocol parser for each device family
- Not feasible on MVP timeline without dedicated network engineer

**GPS data volume management:**
Devices typically report every 10–60 seconds when ignition is on. A fleet of 20 trucks reporting every 30 seconds generates ~58,000 records/day. Storing raw records in PostgreSQL long-term is expensive. Strategy:
- Accept raw position: store to `gps_positions` table (tenant_id, vehicle_id, lat, lng, speed, heading, recorded_at)
- Retain raw data 30 days only; compress older data to 1 record per hour (aggregated track)
- For map display: serve last-known position per vehicle (single row per vehicle from a `vehicle_last_position` materialized view refreshed every 30s)

### Fleet map feature (what to show in browser)

**Table stakes (minimum viable):**
- Vehicle list with last-known position, timestamp, speed
- Static map (Leaflet.js + OpenStreetMap tiles) with vehicle markers
- Vehicle marker shows: plate, status, last-seen-at, speed
- Auto-refresh every 60 seconds (SSE or polling)

**Differentiators (valuable but not required day 1):**
- Historical track replay (draw the trip route on the map from stored positions)
- Geofencing: define polygon zones, trigger alert when vehicle enters/exits
- ETA calculation: current speed + remaining distance → estimate arrival time

**OpenStreetMap note for Mozambique:** OSM coverage in Mozambique is sparse outside Maputo, Beira, and Nampula. Highway routes are mapped but local roads and destinations in rural areas may be missing. Do not attempt route-based ETA calculation outside major corridors. Distance-based ETA (straight-line or known-route distance ÷ average speed) is more reliable.

### Geofencing

A geofence is a polygon stored as a PostGIS geometry or a simplified bounding box. When a GPS position record arrives, check if `ST_Contains(geofence.polygon, ST_MakePoint(lng, lat))` — if the vehicle was outside and is now inside (or vice versa), fire an alert.

**Implementation requirements:**
- PostGIS extension on PostgreSQL (or pure-SQL bounding box approximation if PostGIS not available)
- `geofences` table: `(tenant_id, name, geometry, alert_on_enter, alert_on_exit)`
- Background job (ARQ) runs geofence check on each new position batch
- Alert surfaced in Control Tower and optionally via WhatsApp/email

**Table stakes for geofencing:** Define depot perimeter; alert when a vehicle leaves the depot without a trip being started.
**Differentiator:** Customer-defined delivery zone geofences with ETA notification.

### ETA calculation

ETA requires: known destination, current position, and expected average speed. For ROTAS, the most practical approach:
1. Use the `known_routes` table (already in ROTAS) that stores expected durations per route
2. When GPS position update arrives for an active trip: remaining distance = `known_route.total_distance_km - trip.odometer_km_accumulated`
3. ETA = `now() + (remaining_km / average_speed_last_30min)`
4. Expose as `GET /api/v1/trips/{trip_id}/eta` → `{ eta_minutes: int, confidence: "high" | "low" }`
5. Push ETA to customer portal and optionally WhatsApp notification

**Edge cases:**
- Vehicle stopped (speed=0): ETA is undefined; show "stopped since X" instead
- No GPS data for >30 minutes: ETA confidence = "low"; show last-known ETA
- Trip goes off known route: fall back to straight-line distance calculation
- Clock skew between GPS device and server: always use `server_received_at` for ETA freshness, not device `ts`

### Dependencies
- PostGIS extension or bounding-box-only approach (decide before schema migration)
- `vehicle_gps_devices` table linking IMEI to vehicle
- `gps_positions` table (tenant_id, vehicle_id, lat, lng, speed, heading, recorded_at)
- `vehicle_last_position` materialized view
- ARQ worker for geofence evaluation
- GPS reception endpoint: `POST /api/v1/gps/telemetry/{imei}` (no auth — HMAC-signed or IP-allowlisted)

---

## Feature 2: Despacho Financeiro (Driver Settlement)

**Confidence: HIGH** — Southern African trucking settlement patterns are domain-specific knowledge; the flow is well-understood from freight industry literature.

### How it works in Southern African trucking

The driver settlement cycle in Mozambican / Southern African trucking follows this invariant flow:

```
Trip assigned
    → Cash advance issued (adiantamento)
    → Driver departs, spends cash on route (combustível, portagens, refeições, estadias)
    → Driver records each expense in the app (already partly in ROTAS via trip_costs)
    → Trip ends (delivery proof captured)
    → Driver submits receipt bundle (physical or photo)
    → Manager reconciles: advance − expenses = balance
    → If balance > 0: driver owes money back (common)
    → If balance < 0: company owes driver (less common; means advance was insufficient)
    → Settlement document issued (recibo de despesas de viagem / liquidação de adiantamento)
    → Balance settled by cash or mobile money
```

### The cash advance model (adiantamento)

The advance is issued before departure. In the Mozambican context:
- Small operators: advance paid in cash (MZN notes), sometimes from petty cash
- Larger operators: bank transfer to M-Pesa or e-Mola before departure
- The advance amount is estimated from the trip's expected expenses: fuel cost estimate + tolls + daily allowance (diária) × expected days + contingency
- Advance is pre-approved by fleet manager or operations director

**Data model needed:**
```
trip_advances
  id, tenant_id, trip_id, driver_id
  amount (Numeric 10,2), currency (MZN)
  issued_at, issued_by (user_id)
  payment_method (cash | mpesa | bank | emola)
  mpesa_reference (nullable)
  status (pending | issued | reconciled | disputed)
  notes
```

### Expense recording

Trip costs already exist in ROTAS (`trip_costs` table). The gap is linking them explicitly to the advance:
- Each `trip_cost` entry has `amount`, `category` (fuel, toll, meal, accommodation, other), `receipt_photo_url`
- Driver records expenses in the PWA during the trip (offline-capable, already works)
- At trip close, all `trip_costs` for the trip are summed → `total_expenses`

**Categories that matter for Mozambican routes:**
| Category | Portuguese | Notes |
|---|---|---|
| fuel | combustível | Already tracked separately via fuel_logs; link by reference |
| toll | portagem | Maputo–South Africa EN4 has multiple toll points |
| border fees | taxas de fronteira | Mandatory for cross-border trips; operator-specific amounts |
| meal | refeição | Typically 150–500 MZN/day |
| accommodation | acomodação | When trip is multi-day; typically guesthouses in smaller towns |
| vehicle repair | reparação em viagem | Emergency roadside repair; requires invoice |
| tire | pneu | Punctures are extremely common on Mozambican roads |
| other | outro | Catch-all; requires description + receipt |

### Reconciliation flow

After trip completion:
1. Manager opens the settlement screen for the trip
2. System shows: `Advance issued: 5,000 MZN` vs `Total expenses recorded: 4,200 MZN`
3. Manager reviews each expense line (category, amount, receipt photo)
4. Manager can: approve each expense, dispute (mark as rejected with reason), or request more info
5. On disputed expense: amount is excluded from approved total; driver sees dispute in app
6. Final calculation: `Approved expenses − Advance = Balance`
7. If balance = -800 MZN: driver owes 800 MZN back
8. If balance = +300 MZN: company owes driver 300 MZN

### Settlement document

The settlement document is the output of reconciliation. It must contain:
- Trip reference, dates, driver name, vehicle plate
- Advance issued (amount, date, method)
- Expense line items (category, amount, receipt reference, approved/rejected status)
- Total approved expenses
- Balance to settle (positive = driver owes, negative = company owes)
- Manager signature (digital approval timestamp + name)
- Space for driver acknowledgment (signature line for paper backup)

Generated as PDF (fpdf2 already recommended for billing PDFs — same tool applies here).

### Edge cases in Mozambican context

1. **Driver loses receipts**: Common. Policy decision: require photo receipt for amounts above threshold (e.g., > 500 MZN). Below threshold: manager discretion. Build "no receipt" flag per expense item rather than blocking submission.

2. **Fuel already tracked separately**: The advance includes a fuel component, but fuel_logs have their own detailed records. Link fuel_logs to the advance by trip_id so they don't need to be re-entered as trip_costs. Reconciliation auto-imports fuel totals from fuel_logs.

3. **Multi-day trip with partial reconciliation**: Driver needs interim cash (ran out mid-trip). Extend the model to allow multiple advances per trip (advance_sequence: 1, 2, ...). Each advance linked to the trip. Reconciliation sums all advances.

4. **Currency: MZN, ZAR, USD mix**: Cross-border trips (Mozambique → South Africa) involve ZAR expenditure. Tolls on EN4 may be paid in ZAR. The expense form must support: amount + currency. The settlement document converts all to MZN at the exchange rate specified at reconciliation time (manager sets rate manually — no live FX required for MVP).

5. **Driver disputes the reconciliation**: Manager rejects an expense; driver disagrees. Add a dispute state on individual expense items with a comment thread (one round trip is sufficient for MVP). Escalation to admin if not resolved.

6. **Advance not issued (driver self-funded)**: Some owner-operators pay from personal funds and claim reimbursement. Support `advance_amount = 0` with balance always negative (company owes driver).

7. **Vehicle breakdown cost**: Emergency repair on the road. Amount may be large (>1,000 MZN). Requires additional approval step (manager must approve high-value emergency expenses separately before reimbursing).

### Table stakes vs differentiators

**Table stakes:**
- Advance registration before departure
- Expense recording per trip (already partly exists)
- Reconciliation calculation (advance − approved expenses)
- Settlement document PDF

**Differentiators:**
- Multi-currency support (MZN + ZAR + USD)
- Per-expense approval/dispute workflow
- Automatic fuel cost import from fuel_logs
- WhatsApp notification when settlement is approved or disputed

**Anti-features:**
- Driver payroll integration — out of scope; this is trip expense settlement, not HR
- Bank feed / automatic reconciliation — no bank API access in Mozambique

### Dependencies
- `trip_advances` table (new)
- Settlement status on `trips` table (add `settlement_status` field)
- PDF generation (fpdf2 — already recommended)
- ARQ for notification on settlement approval
- Auth: only fleet manager or owner role can approve settlement; driver sees read-only view

---

## Feature 3: Customer Portal (Shipment Tracking)

**Confidence: MEDIUM-HIGH** — anonymous tracking portal patterns are standard SaaS; token security is well-understood.

### What data to expose

The customer (consignee / remetente) needs to answer: "Where is my cargo? When will it arrive?"

**Minimum data set (table stakes):**
- Trip status: in progress / completed / delayed
- Current vehicle position (last GPS ping) — city/region level, not precise coordinates
- Expected delivery date (from trip order)
- Estimated time of arrival (if GPS integration is active)
- Last stop location and time
- Delivery proof status: pending / delivered + timestamp + delivery address

**What NOT to expose (privacy / operational security):**
- Exact GPS coordinates in real-time (enables cargo theft planning)
- Driver name and phone number (personal data; not the customer's business)
- Other trips or vehicles in the fleet (tenant data isolation)
- Internal costs, advance, reconciliation data
- Vehicle plate (optional: some operators want to hide this; make it configurable)

### How competitors handle it (MEDIUM confidence from training data)

Major LTL carriers (DHL Freight, Maersk, Kuehne+Nagel) use:
- A unique tracking number issued per shipment (bill of lading number)
- Public-facing URL: `https://track.carrier.com/T-2024-ABC123`
- Anonymous access — no login required
- Page shows status timeline, last scan point, ETA
- Optional: email/SMS subscribe for status updates

SME fleet platforms (Onfleet, Circuit, Tookan) typically:
- Generate a customer-facing tracking link per delivery
- Expose a live map with driver position (within ~500m accuracy, intentionally imprecise)
- Include recipient name, estimated window, delivery photo

**For ROTAS:** Simple public tracking page per trip (or per cargo manifest), accessible via a token-based URL. No login required.

### Token design

**Requirement:** Token must be shareable (sent via WhatsApp/email), non-guessable, and scoped to exactly one shipment.

**Recommended approach:**
```
tracking_tokens
  id (UUID)
  tenant_id
  trip_id (FK)
  cargo_manifest_id (nullable — for multi-manifest trips)
  token (128-bit random hex, stored as SHA-256 hash)
  created_at
  expires_at (nullable — some operators want permanent tracking links)
  revoked (boolean)
  view_count (for analytics)
```

Token generation:
```python
import secrets, hashlib

def generate_tracking_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)      # 256 bits, URL-safe base64
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed                   # store hashed, share raw
```

Tracking URL: `https://track.rotas.mz/T/{raw_token}` or `https://manager.rotas.mz/rastreio/{raw_token}`

**Security properties:**
- `secrets.token_urlsafe(32)` produces 256 bits of entropy — brute force infeasible
- Server stores only the SHA-256 hash; raw token never persisted (same as password handling)
- On lookup: SHA-256 the incoming token, query by hash
- Rate-limit the tracking endpoint: 60 requests/minute per IP (prevent enumeration)
- Tokens expire after trip completion + 30 days (configurable per tenant)
- `view_count` increment on each access (detect unusual access patterns)

### Page design for Mozambique context

The tracking page will be opened on the customer's mobile browser. Mozambique customers will primarily use:
- Low-end Android browsers (Chrome Lite / Samsung Internet)
- Shared mobile data connections
- Low digital literacy in some segments

**Page requirements:**
- Single-page, < 50KB total (no heavy map JS if GPS is not integrated yet)
- Status in Portuguese with large, clear icons
- Timeline: Order received → In transit → Out for delivery → Delivered
- Current location: text only ("Última posição: EN4 km 300, Moamba — há 2 horas")
- Delivery confirmation photo (if available)
- Manager contact number (optional — tenant configures whether to expose)
- No login wall, no sign-up prompt

**When GPS is integrated:** add a simple Leaflet map (< 200KB gzipped, OSM tiles) showing a circle at the vehicle's approximate position with a 5km radius (intentional imprecision).

### Shareable link generation flow

1. Manager creates a trip order and links cargo manifest
2. System auto-generates a tracking token when the trip starts (status transitions to "in_progress")
3. Manager sees the tracking URL in the trip detail view with a "Copy Link" button and a "Share via WhatsApp" deep link
4. Manager shares with customer (copy-paste into WhatsApp, or ROTAS sends it automatically via WhatsApp API)
5. Customer opens URL on mobile — sees tracking page
6. Page auto-refreshes every 5 minutes (simple meta-refresh or polling; no WebSocket needed)

### Edge cases

1. **Trip not started yet**: Show "Awaiting dispatch" — do not expose internal trip status details
2. **Trip cancelled**: Show "Shipment cancelled — contact [manager phone]"
3. **GPS not integrated**: Show status-only view (no map, no precise location) — this is the initial state
4. **Multiple deliveries on one trip (multi-stop)**: Issue a token per cargo manifest, or show all stops on one tracking page with individual statuses
5. **Customer shares the link publicly**: No issue — 256-bit token, no sensitive data beyond cargo status
6. **Token expiry after delivery**: Return a "Shipment delivered on [date]" static page — do not 404 (confusing for customers)

### Dependencies
- `tracking_tokens` table
- Public-facing route on Next.js manager app: `/rastreio/[token]` (no auth middleware)
- Rate limiting on tracking endpoint (slowapi on FastAPI, or Vercel edge middleware)
- GPS integration (for map view — optional at launch)
- WhatsApp integration (for sharing link — optional at launch; manual share works)

---

## Feature 4: WhatsApp Business Notifications

**Confidence: MEDIUM** — Meta API and provider landscape are known from training; Mozambique-specific provider availability is LOW confidence without current market data.

### Meta Cloud API vs Twilio vs 360dialog

**Meta WhatsApp Business Cloud API (direct):**
- Free to use (Meta does not charge for the API itself)
- Per-conversation pricing: ~ $0.003–0.006 USD per conversation (varies by country)
- Mozambique is in the pricing tier for "Africa" — pricing is moderate
- Requires: Facebook Business Manager account, approved Business name, phone number verified, message templates approved by Meta
- Template approval takes 24–72 hours; new templates must be pre-approved
- Rate limit: 1,000 conversations/day on new numbers; scales to unlimited after 6 months
- REST API: POST to `https://graph.facebook.com/v18.0/{phone_number_id}/messages`

**Twilio WhatsApp Business:**
- Twilio resells WhatsApp Business access
- Higher per-message cost than direct (Twilio margin on top of Meta fees)
- Better developer experience, more abstractions, richer SDK
- Mozambique: Twilio has MZ coverage but verify current availability
- For a cash-conscious startup: direct Meta API is cheaper

**360dialog:**
- WhatsApp Business Solution Provider (BSP) focused on emerging markets
- Simpler onboarding than direct Meta (360dialog handles Business Manager verification)
- Used by many African SaaS companies for WhatsApp integration
- Monthly fee per phone number ($45–$100/month) + per-message costs
- **Recommendation for ROTAS:** 360dialog is the pragmatic choice for first 6 months because it accelerates onboarding; switch to direct Meta Cloud API once message volume justifies the cost savings

**Recommended: 360dialog for launch, plan migration to direct Meta Cloud API at scale**

### Message templates required

WhatsApp Business requires pre-approved templates for outbound messages (messages initiated by the business, not replies to customer messages). Templates are fixed text with variable parameters.

**Required templates for ROTAS v2.0:**

| Template Name | Trigger | Content | Variables |
|---|---|---|---|
| `trip_dispatched` | Trip status → in_progress | "A viagem {{1}} foi iniciada. O motorista {{2}} partiu de {{3}} às {{4}}." | trip_ref, driver_name, origin, time |
| `delivery_completed` | Delivery proof captured | "A carga {{1}} foi entregue em {{2}} às {{3}}. Comprovante: {{4}}" | cargo_ref, destination, time, tracking_url |
| `eta_update` | ETA recalculated | "A viatura {{1}} está em rota. Estimativa de chegada: {{2}}." | vehicle_plate or trip_ref, eta_time |
| `document_expiring` | Compliance check (scheduled) | "Atenção: O documento {{1}} da viatura {{2}} vence em {{3}} dias." | document_type, vehicle_plate, days_remaining |
| `settlement_approved` | Settlement status change | "A liquidação da viagem {{1}} foi aprovada. Saldo: {{2}} MZN." | trip_ref, balance |
| `settlement_disputed` | Manager disputes an expense | "A despesa de {{1}} MZN ({{2}}) na viagem {{3}} foi questionada. Motivo: {{4}}" | amount, category, trip_ref, reason |
| `driver_blocked` | Driver compliance block | "O motorista {{1}} está bloqueado para partida. Documento em falta: {{2}}" | driver_name, document_type |

**Template approval notes:**
- All templates must be in Portuguese (or the business language declared to Meta)
- "Call to action" buttons are allowed (e.g., "Ver rastreio" → opens tracking URL)
- No promotional content in operational templates (Meta rejects marketing in utility templates)
- Approval time: 1–3 business days typical; allow 1 week buffer before launch

### Recipients

| Notification | Recipient | Channel |
|---|---|---|
| Trip dispatched | Customer (cargo recipient) | WhatsApp + tracking link |
| Delivery completed | Customer + Fleet manager | WhatsApp |
| ETA update | Customer | WhatsApp |
| Document expiring | Fleet manager | WhatsApp |
| Settlement approved/disputed | Driver | WhatsApp |
| Driver blocked | Fleet manager | WhatsApp |

**Driver WhatsApp number:** Capture as part of driver profile (drivers in Mozambique nearly universally have WhatsApp on their primary SIM). Already feasible given `drivers.phone_number` likely exists.

### Implementation architecture

```
ARQ worker (notification_task)
  ← triggered by: trip status change, delivery proof capture, settlement approval, compliance check cron
  → POST https://graph.facebook.com/v18.0/{phone_id}/messages
  → body: { to: recipient_phone, type: "template", template: { name, language, components } }
  → on 4xx: log and dead-letter (no retry on invalid template)
  → on 5xx or rate limit: retry with exponential backoff (3 attempts)
```

Phone number format: WhatsApp requires E.164 format. Mozambican numbers: +258 8X XXX XXXX. Validate on entry.

**Fallback:** If WhatsApp delivery fails (number not on WhatsApp, opt-out, etc.), fall through to email (SendGrid/Resend) if the contact has an email address. Email is secondary in the Mozambican market but should be available for managers (who typically have corporate email).

### Edge cases

1. **Recipient not on WhatsApp**: API returns error code 131047 ("Phone number is not a registered WhatsApp number"). Silently fail + log; do not retry.
2. **Customer opts out**: Meta sends a webhook on opt-out. Store `whatsapp_opted_out: true` on the contact record. Never send to opted-out numbers.
3. **Template rejected by Meta**: Log and alert the ROTAS admin. Fallback to email for that notification type until template is re-submitted.
4. **Rate limit (new number)**: 1,000 conversations/day initial limit. For a fleet with 20 active trips/day generating 3-4 messages each, this limit is hit by Day 20 of operation. Plan the Meta tier upgrade process proactively.
5. **Manager wants to receive notifications in English, not Portuguese**: Template language is declared at template level, not per-send. Create duplicate templates in English if needed.
6. **Mozambique phone number format variations**: Some drivers store numbers as `85 123 4567` (local), `+258851234567` (E.164), or `00258851234567` (international with leading zeros). Normalize all to E.164 on save.

### Dependencies
- ARQ worker (already recommended for architecture)
- `notification_log` table: `(tenant_id, recipient_phone, template_name, sent_at, status, error_code)`
- WhatsApp Business Account credentials in environment variables: `WHATSAPP_PHONE_ID`, `WHATSAPP_ACCESS_TOKEN`
- Template pre-approval (do this first — blocks all notification launch)
- Driver `phone_number` field validation (E.164 normalization)
- Customer/contact phone on contracts or trip orders

---

## Feature 5: Self-Service Onboarding

**Confidence: HIGH** — SaaS onboarding patterns are well-established; Mozambique-specific payment context is MEDIUM confidence.

### What a new tenant registration flow needs

**Minimum flow (table stakes):**

```
Landing page (marketing)
  → "Começar gratuitamente" CTA
  → Registration form
  → Email verification
  → Company setup wizard
  → (Trial starts)
  → Plan selection + payment (or defer to sales call)
  → Active tenant
```

**Registration form fields:**
- Company name (Razão Social)
- NIT/NUIT (tax identification number — required for invoice issuance in Mozambique)
- Contact name (first + last)
- Email address (becomes owner account)
- Phone number (WhatsApp — for onboarding support)
- Password (bcrypt, min 12 chars)
- Terms of service acceptance (checkbox + timestamp)

**Do NOT collect on registration:**
- Fleet size (ask during wizard, not gating registration)
- Credit card (defer to plan selection after trial)
- Logo/branding (nice to have, not blocker)

### Trial period

**Recommendation: 14-day free trial, full feature access, no credit card required.**

Rationale for Mozambican market:
- SME decision cycles are long and involve multiple stakeholders (owner, accountant, operations manager)
- Trust is low for SaaS from non-local companies; a 30-day no-risk trial removes the main objection
- 14 days is sufficient to complete 2-3 trip cycles and see the value
- Longer trials (30+ days) reduce conversion urgency

**Trial mechanics:**
- `tenants.trial_ends_at` timestamp; `tenants.plan` = "trial"
- Full feature access during trial
- Warning banners at 7 days, 3 days, 1 day remaining
- After trial expires: read-only mode (can view historical data, cannot create new trips/dispatches)
- Grace period: 3 days after trial expiry before read-only kicks in (prevents losing a customer on a weekend)

### Plan selection

**Recommended pricing tiers for Mozambique context (MEDIUM confidence — no market validation):**

| Plan | Price (MZN/month) | Vehicles | Drivers | Features |
|---|---|---|---|---|
| Básico | 2,500–5,000 MZN (~$40–80 USD) | 5 | 10 | Core trip + compliance |
| Profissional | 7,500–12,000 MZN (~$120–190 USD) | 20 | 50 | + GPS + settlement + portal |
| Empresarial | Custom | Unlimited | Unlimited | + API + white-label |

Note: Mozambique GDP per capita ~$600/year; small transportadoras are cash-constrained. A $40/month starting price is meaningful. Consider pricing in MZN to avoid FX exposure for customers.

**Enforcement mechanics:**
- `tenants.max_vehicles`, `tenants.max_drivers`, `tenants.max_users` columns already exist on `Tenant` model (per PROJECT.md)
- Soft limit: warning when within 80% of limit ("15 of 20 vehicles used")
- Hard limit: 409 error from API when limit is reached; frontend shows upgrade prompt
- Plan limits enforced in service layer (`vehicles/service.py` before INSERT: `if vehicle_count >= tenant.max_vehicles: raise ApiError(...)`)

### Payment

**Critical constraint:** Mozambique has limited payment infrastructure for B2B SaaS subscriptions.

**Payment options in Mozambique B2B context (MEDIUM confidence):**
1. **Bank transfer (TPA / RTGS)**: Standard for B2B; manual reconciliation required on ROTAS side; monthly invoice → payment within 30 days
2. **M-Pesa Business**: Widely used; supports B2B payments; Vodacom M-Pesa has a Business API (requires Vodacom partnership agreement)
3. **e-Mola**: Alternative mobile money (Movitel); smaller market share than M-Pesa
4. **Stripe**: Not available in Mozambique as a payment method for customers (Stripe supports collecting from MZ customers only if ROTAS is incorporated in a Stripe-supported country)
5. **Flutterwave / Paystack**: African payment platforms; both support Mozambique as a collection market; API integration is straightforward; recommended for automated billing

**Recommended MVP payment approach:**
- Launch with **manual bank transfer + invoice** (no payment gateway code needed)
- Integrate Flutterwave for automated card/mobile money billing in v2.1
- Stripe for any international customers paying in USD/EUR (ROTAS entity must be outside MZ for Stripe to process)

### Company setup wizard

After registration, a guided wizard before first use:
1. **Fleet setup**: "How many vehicles do you have?" → Add 1-3 vehicles now (import from spreadsheet later)
2. **Driver setup**: "Add your first driver" (name, license, phone)
3. **Compliance config**: "Which documents do you track?" (pre-populated with Mozambique defaults: INATTER, insurance, registration)
4. **First trip**: Guided tour of creating a trip order (can skip)
5. **Invite teammates**: Add a second manager/admin user (optional)

Wizard progress stored per tenant; can be resumed. Do not gate app access on wizard completion.

### Edge cases

1. **NUIT validation**: Mozambique NUITs are 9 digits. Validate format but not against AT database (no public API). Accept with warning if format incorrect.
2. **Company already exists**: Check by company name or NUIT for duplicate detection. Suggest "Contact us if your company already has an account."
3. **Email not verified**: Allow starting wizard but block first operational action (creating a trip) until email is verified. Send verification resend up to 3 times.
4. **Owner loses access to email**: Recovery via phone number (WhatsApp verification code) — this requires WhatsApp integration to be live.
5. **Trial extension request**: Common. Build a manual override: admin can extend `trial_ends_at` from a super-admin panel (ROTAS internal tooling, not exposed to tenants).
6. **Free plan (permanent)**: Consider a permanent free tier with limits (1 vehicle, 1 driver, 5 trips/month) for the "pilot a small fleet owner" use case. Reduces friction; converts to paid when fleet grows.

### Dependencies
- `tenants` table already exists; needs: `trial_ends_at`, `plan`, `onboarding_completed_at`, `nuit`
- `tenant_plan_limits` or limits fields on `Tenant` model (already have `max_vehicles`, etc.)
- Email verification flow (new: send verification email via Resend/SendGrid)
- New public routes on Next.js manager app (no auth): `/registo`, `/verificar-email`, `/planos`
- Tenant creation API: `POST /api/v1/tenants` (currently admin-only; needs a public variant with captcha)
- reCAPTCHA or hCaptcha on registration form (prevent automated tenant creation)
- Super-admin panel (internal only): view all tenants, extend trials, manage plans

---

## Feature 6: Conflict Resolution UI (Sync)

**Confidence: HIGH** — pattern well-researched in ARCHITECTURE.md; UX for low-literacy drivers is specific domain knowledge at MEDIUM confidence.

### How offline sync conflicts happen in fleet management

In ROTAS's model, conflicts arise when:
1. Driver edits an entity offline (e.g., corrects a fuel amount recorded incorrectly)
2. Meanwhile, a manager edits the same entity in the dashboard (e.g., adjusts the same fuel entry after a receipt scan)
3. Driver's device reconnects and pushes the update via sync batch
4. Server sees: `device sent version 3, server currently has version 4` → conflict

More commonly in practice:
- Driver submits a fuel log offline → sync succeeds
- Driver notices an error and tries to edit the same log while offline
- Second sync: the update arrives with `base_version = 1` but server already has `version = 1` (no actual conflict — just needs a re-read from server first)

**ROTAS-specific reality check:** With a single driver per device, true simultaneous edit conflicts are rare. The most common "conflict" scenario is:
- Failed sync item (network drop mid-sync)
- Driver-edited-offline update for a record the manager has since approved/finalized
- Idempotency key collision (already mitigated by tenant-namespace keys)

### Recommended resolution strategy (from ARCHITECTURE.md)

- Server-authoritative versioning with field-level merge
- For append-only data (trip stops, checklist answers, expense items): conflicts are impossible; server accepts INSERT unconditionally
- For update operations: server-wins on same-field conflicts; driver's offline data is recorded in `conflict_log` for manager review

### Driver UI for conflict — design for low digital literacy

**Key constraint:** Many Mozambican truck drivers have low digital literacy. Complex conflict resolution UIs (showing diffs, merge tools) will confuse them and cause anxiety about their data.

**Recommended UX approach:**

**Step 1: Don't show conflict detail to driver**
The driver should see only: "X items could not be synced. A gestora foi notificada." (X items could not sync. The manager was notified.)

- No technical jargon ("version conflict", "merge failure")
- Number of affected items
- Manager notification auto-sent
- "Retry" button (retries the sync)
- "Pedir ajuda" (Ask for help) → opens WhatsApp to manager phone

**Step 2: Manager resolves in dashboard**
The conflict is surfaced to the manager, not the driver. Manager sees:

```
Conflito de sincronização — Viagem #V-2024-042
Motorista: António Machava
Item em conflito: Registo de combustível
  Valor enviado pelo motorista (offline): 350 L — 12.500 MZN
  Valor actual no sistema: 340 L — 12.000 MZN
  [Aceitar versão do motorista] [Manter versão actual] [Editar manualmente]
```

Manager makes the decision; driver is informed of outcome via WhatsApp notification.

**Step 3: Auto-resolution rules (reduce manager burden)**
For categories where business rules are unambiguous, auto-resolve:
- Trip stop append (new stop added offline, not conflicting with existing): auto-accept
- Checklist response (append-only): auto-accept
- Fuel log CREATE (new record, not update): auto-accept (idempotency handles duplicates)
- Fuel log UPDATE with same values: auto-accept (idempotent)
- Fuel log UPDATE with different values: route to manager

**Show conflict count in Control Tower**: "3 conflitos pendentes de resolução" as a KPI card. Clicking opens the conflict resolution queue.

### Data model for conflict tracking

```
sync_conflicts
  id (UUID)
  tenant_id
  trip_id (nullable)
  entity_type (fuel_log | trip_cost | checklist | ...)
  entity_id
  device_id (which driver device sent the conflicting update)
  driver_id
  client_payload (JSONB — what the driver sent)
  server_payload_at_conflict (JSONB — what the server had)
  base_version (int — what version driver thought it was editing)
  server_version (int — actual server version at conflict time)
  resolution (pending | accepted_client | accepted_server | manual_edit | auto_resolved)
  resolved_by (user_id nullable)
  resolved_at (timestamp nullable)
  created_at
```

### Driver sync status badge

Every screen in the driver PWA should show a persistent sync status badge:
- Green dot: "Tudo sincronizado" (all synced)
- Orange dot with number: "3 pendentes" (3 items pending sync — waiting for network)
- Red dot with number: "2 conflitos" (2 conflicts — need manager attention)

The badge should be tappable and open a list: "3 registos aguardam sincronização" with item types (e.g., "Abastecimento", "Paragem").

This is table stakes for driver confidence. Without it, drivers cannot tell if their data is lost or pending.

### Edge cases

1. **Device has no connectivity for 5+ days**: Dexie queue accumulates. On reconnect, a large batch fails due to expired idempotency keys (30-day TTL). Pre-emptively warn driver after 3 days offline: "Sync pendente — conectar à internet em breve."
2. **Conflict on delivery proof**: Delivery proof is the billing trigger. If the manager-side version is marked "validated" and the driver pushes a conflict, auto-accept manager version (billing is in progress). Flag for manager review.
3. **Driver edits a closed trip**: Trip is marked "completed" server-side; driver sends a fuel log update for the same trip offline. Reject with a clear error: "Esta viagem já foi encerrada. Contacte a gestora."
4. **Conflict storm**: Driver pushes 50 conflicting updates at once (e.g., after 7 days offline with many manager edits). Show manager a batched conflict resolution list; allow "Accept all client" or "Accept all server" bulk actions.

### Dependencies
- `sync_conflicts` table (new)
- `server_version` integer column on all syncable entities
- `base_version` field in sync batch payload
- Manager-facing conflict resolution UI (Next.js component)
- Sync status badge in driver PWA (Vite/React component)
- WhatsApp notification on conflict (uses notification infrastructure)
- Control Tower KPI card: "pending conflicts count"

---

## Feature 7: Tenant Limits Enforcement

**Confidence: HIGH** — SaaS limit enforcement patterns are well-established; specific UX patterns are MEDIUM confidence.

### What limits to enforce

The `Tenant` model already has `max_vehicles`, `max_drivers`, `max_users`. The gaps are:
1. No enforcement in service layer
2. No UX for approaching / hitting limits
3. No differentiation between soft limits (warn) and hard limits (block)

**Full list of limits that matter for ROTAS:**

| Limit | Current State | Enforcement Type |
|---|---|---|
| max_vehicles | Field exists, unenforced | Hard — block vehicle creation at limit |
| max_drivers | Field exists, unenforced | Hard — block driver creation at limit |
| max_users (manager accounts) | Field exists, unenforced | Hard — block user invitation at limit |
| max_trips_per_month | Not implemented | Soft — warn at 80%; hard block at 100% |
| storage_gb | Not implemented | Soft — warn at 80% of plan allocation |
| data_retention_days | Not implemented | Platform-enforced (scheduled deletion job) |

### Soft limit (warning) UX pattern

When a resource count reaches 80% of the plan limit:
- Show a banner in the manager dashboard: "Você está usando 16 de 20 viaturas incluídas no seu plano. Actualizar plano para adicionar mais."
- Banner is dismissable but re-appears on next login
- No blocking behavior
- Link to plan upgrade page

**Implementation:** On every page load of the dashboard layout, call a lightweight `GET /api/v1/tenant/limits` endpoint that returns `{ vehicles: { used: 16, max: 20, pct: 80 }, ... }`. Cache in Redis with 5-minute TTL. Show banner if any resource is >= 80%.

### Hard limit (block) UX pattern

When a resource count reaches 100% of the plan limit:

**API response:** Return `HTTP 403` (not 422 or 400 — this is authorization, not validation) with body:
```json
{
  "error": "plan_limit_reached",
  "detail": "O limite do seu plano de 20 viaturas foi atingido.",
  "limit_type": "vehicles",
  "current": 20,
  "max": 20,
  "upgrade_url": "https://app.rotas.mz/plano/actualizar"
}
```

**Frontend response:**
- Show a modal (not a toast — must be acknowledged): "Limite de viaturas atingido. Para adicionar mais, actualize o seu plano."
- Primary button: "Ver planos" → redirect to /planos
- Secondary button: "Cancelar"
- Do not allow the action to proceed (form should not submit)

**Critical UX rule:** The block must happen BEFORE the user fills out a long form and submits. Show the block indicator on the "New vehicle" button before they start typing — change button state to "Limite atingido" with an info icon. Clicking the button opens the upgrade modal without navigating away.

### Enforcement in service layer

Pattern for vehicle creation (replicate for all limited resources):

```python
# backend/app/modules/vehicles/service.py

async def create_vehicle(db: AsyncSession, tenant_id: str, data: VehicleCreate) -> dict:
    # Enforce plan limit FIRST — before any other validation
    tenant = await _get_tenant(db, tenant_id)
    vehicle_count = await db.scalar(
        select(func.count(Vehicle.id)).where(Vehicle.tenant_id == tenant_id)
    )
    if vehicle_count >= tenant.max_vehicles:
        raise ApiError(
            code="plan_limit_reached",
            message=f"O limite de {tenant.max_vehicles} viaturas foi atingido.",
            status_code=403,
            extra={"limit_type": "vehicles", "current": vehicle_count, "max": tenant.max_vehicles}
        )
    # ... rest of create logic
```

**Important:** The `max_vehicles` check query must include `WHERE tenant_id = :tenant_id` to count only this tenant's vehicles (tenant isolation requirement — cannot accidentally count another tenant's vehicles).

### Grace period on plan downgrade

When a tenant downgrades from Professional (20 vehicles) to Básico (5 vehicles) but currently has 15 vehicles:
- Do NOT immediately block or delete existing vehicles
- Set a 30-day grace period: `tenants.grace_period_ends_at`
- During grace period: existing resources remain accessible; new ones are blocked above the new plan limit
- After grace period: read-only for resources above limit (can view but not edit or create trips for those vehicles)
- Notification at 14 days, 7 days, 3 days before grace period ends via email + WhatsApp

### Trial expiry enforcement

When trial ends:
- `tenants.plan = "expired"`
- All mutation endpoints return 403 with `error: "trial_expired"`
- All GET/list endpoints still work (read-only access)
- Dashboard shows full-screen banner: "Seu período de teste terminou. Activar plano para continuar a usar o ROTAS." with plan options
- Do not delete data during grace period (7 days)

### Edge cases

1. **Race condition on limit check**: Two concurrent requests both pass the count check under the limit; both succeed. This creates `max + 1` vehicles. Mitigate: use a `SELECT FOR UPDATE` on the tenant row during the count check, or use a database constraint (`CHECK (vehicle_count <= max_vehicles)` via triggers). The simpler approach: idempotent re-check after INSERT — if over limit, delete the just-inserted row and return 403.

2. **Importing a fleet from spreadsheet**: Batch import of 20 vehicles where the limit is 5. The import should pre-check the batch size vs remaining capacity and reject the entire import upfront with a clear message: "Pode importar no máximo 5 viaturas com o seu plano actual (usou 0 de 5)."

3. **Admin override**: ROTAS super-admin should be able to set `max_vehicles = 999` for special customers (large fleets on enterprise plan, pilot customers). This should be in the super-admin panel with a note field for the reason.

4. **Limit not set (null)**: `max_vehicles = null` should mean "unlimited" (enterprise plan behavior). The enforcement code must check for null: `if tenant.max_vehicles is not None and vehicle_count >= tenant.max_vehicles`.

5. **Soft limit notification delivery**: The 80% warning should be sent via WhatsApp/email once, not on every page load. Store `limit_warning_sent_at` per resource type on the tenant record to prevent notification spam.

### Dependencies
- Service layer enforcement in all limited-resource create endpoints
- `GET /api/v1/tenant/limits` endpoint (new; cached in Redis)
- Manager dashboard layout: limit banner component
- "New resource" button: disabled state with upgrade CTA when at limit
- Upgrade modal component (reusable)
- Plan management admin panel (ROTAS internal)
- ARQ scheduled job: daily scan for tenants approaching limits → send notification

---

## Feature 8: Client Registry and Accounts Receivable

**Confidence: HIGH for A/R patterns (well-established accounting domain); MEDIUM for Mozambique-specific tax/compliance nuances.**

_Note: This feature is the focus of milestone v2.0 — "Gestão de Clientes e Contas a Receber". Features 1–7 above are future milestone features. Feature 8 is the active work item._

### Current state gap

`Contract.client_name` is a free-text `String(160)`. There is no `Client` entity. The consequences:
- No deduplication: "Cimentos de Moçambique" and "Cimentos de Mozambique" are different clients in the system
- No NUIT on record: invoices cannot include the client's NUIT (required for Mozambique tax compliance)
- No payment terms per client: every contract has the same implicit terms
- No credit limit: no way to block new trips for a client with unpaid invoices over the limit
- No running balance: each `BillingDocument` is isolated; there is no client-level view of total outstanding
- Multi-contract invoicing impossible: one invoice per contract, not per client

### What "client entity" means in B2B logistics

A client (cliente) in logistics SaaS is a business entity, not a person. In Mozambique:
- Always a company (NUIT is a legal entity identifier, not personal)
- May have multiple contracts with the transporter (different routes, different vehicle classes, different pricing)
- Has a primary contact (gestor de conta or responsável financeiro)
- Has agreed payment terms (30, 45, or 60 days after invoice date — 30 days is standard in Mozambique B2B logistics)
- May have a credit limit (maximum outstanding balance before new services are blocked)
- Has a registered address (required on invoices per Mozambique tax law)

---

### Category A: Client Registry (Cadastro de Clientes)

**Table stakes — must ship:**

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Client entity with NUIT | Tax compliance — NUIT required on invoices since 2025 AT mandate | LOW | 9-digit numeric validation; not validated against AT database (no public API) |
| Company name + trade name | Razão social vs nome comercial differ for many MZ companies | LOW | Two name fields: `legal_name` (Razão Social) and `trade_name` (optional) |
| Primary contact (name, email, phone) | Point of contact for invoice disputes and payment follow-up | LOW | Single contact at MVP; multiple contacts is differentiator |
| Billing address | Required on invoice by MZ tax law | LOW | Street, city, province (Mozambique has 11 provinces) |
| Payment terms (days) | Determines invoice due date calculation | LOW | Default 30 days; options: 15, 30, 45, 60, 90 |
| Client status (active / inactive / suspended) | Suspended clients should block new trip dispatch | MEDIUM | Status check in trip dispatch service |
| Contract-to-client FK migration | `Contract.client_name` → `Contract.client_id` without data loss | MEDIUM | Requires Alembic migration + backfill strategy (auto-create client per unique `client_name`) |

**Differentiators — valuable but not MVP-blocking:**

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Credit limit with enforcement | Block new trips when client balance exceeds limit | MEDIUM | Requires real-time outstanding balance query; adds latency to trip dispatch |
| Multiple contacts per client | Different contacts for finance vs operations | LOW | `client_contacts` table; PRIMARY contact required, others optional |
| Client category / segment | "Mining", "Retail", "Government" — useful for reporting | LOW | Tag or enum on client; no enforcement logic required |
| Client notes / history | Free text field for CRM-style notes | LOW | Simple `notes: Text` field; no versioning needed at MVP |
| Client portal login | Client self-service to view invoices and statements | HIGH | Full authentication flow; deferred to future milestone |

**Anti-features:**

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| AT NUIT validation via API | Seems like good validation | No public AT API exists; would require partnership with AT; blocks registration if API is down | Validate format only (9 digits numeric); flag invalid format visually |
| CRM pipeline / sales funnel | Clients are existing customers, not prospects | Wrong product category; adds complexity without logistics value | Keep client registry operational; link to external CRM if needed |
| Client self-service portal (MVP) | Clients want to view their own invoices | Full auth flow + separate UI; doubles scope | Generate PDF and email/WhatsApp to client contact instead |
| Automatic credit hold | Auto-suspend trips when limit exceeded | Creates operational emergencies if a late payment coincidentally blocks a trip already in progress | Soft warning only; manager approves suspension manually |

---

### Category B: Multi-Contract Invoicing (Faturação Multi-Contrato)

**Current state:** One `BillingDocument` per `Contract` per period. A client with 3 contracts in January gets 3 separate invoices.

**Target state:** One invoice per client per period, aggregating trips across all contracts.

**Table stakes — must ship:**

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Invoice grouped by client_id | Standard in B2B: one invoice = one client = one payment | MEDIUM | `BillingDocument` needs `client_id` FK alongside/instead of `contract_id` |
| Multiple contracts on same invoice | Client may have contract for Maputo routes AND contract for Beira routes | MEDIUM | `BillingDocument` → `BillingItem` already supports multiple contract_ids; the grouping key changes |
| Invoice number sequence per tenant | Invoices need sequential numbering (AT requirement from 2025) | LOW | `invoice_number: String` with format `YYYY/NNNN`; sequence per tenant; never reuse |
| Client NUIT on invoice PDF | Required by Mozambique AT since May 2025 mandate | LOW | Pull from `Client.nuit` when generating PDF |
| Invoice due date from payment terms | `due_date = issued_at + client.payment_terms_days` | LOW | Computed field on invoice; surfaced in A/R aging |

**Differentiators:**

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Invoice grouping by contract sub-totals | Within one invoice, show a sub-total per contract | LOW | Visual grouping in PDF; no schema change needed |
| Invoice amendment / credit note | If a trip is disputed after invoice is issued | HIGH | Full credit note workflow; deferred to v3 |
| Proforma invoice | Issue a draft invoice for client approval before finalizing | MEDIUM | Status addition: `proforma` before `issued`; useful for large clients |

**Anti-features:**

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Invoice splitting (one trip on multiple invoices) | Edge case request | Complicates trip billing status machine significantly | One trip = one invoice only; reassign if wrong invoice |
| Retroactive period changes | Reopening a closed period to add a trip | Creates accounting inconsistency | New period or invoice amendment workflow only |

---

### Category C: Payment Registration (Registo de Pagamentos)

**Table stakes — must ship:**

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Register a payment against an invoice | Closes the A/R loop; without this, all invoices are perpetually "outstanding" | LOW | `PaymentRecord` table: `(tenant_id, billing_document_id, client_id, amount, payment_date, method, reference)` |
| Partial payment support | Common in MZ B2B: client pays 50% of invoice now, rest in 15 days | LOW | `payment_amount <= invoice.total_amount`; invoice status moves to `partially_paid` |
| Overpayment handling | Client pays 110% of invoice (advance or accounting error) | LOW | Record overpayment; flag for review; do not auto-apply to next invoice at MVP |
| Payment methods | Bank transfer (TPA/RTGS), M-Pesa, e-Mola, cash, cheque | LOW | Enum field; no payment gateway integration needed; manager records manually |
| Payment reference | Bank reference number or M-Pesa transaction ID | LOW | Free text `reference` field; used for reconciliation |
| Value date vs record date | `payment_date` (when client paid) vs `recorded_at` (when manager entered it) | LOW | Two timestamp fields; `payment_date` is what matters for aging |
| Invoice status transitions | draft → issued → partially_paid → paid → overdue | LOW | Status computed or stored; `overdue` set by `due_date < today AND status != paid` |

**Differentiators:**

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Payment-to-invoice auto-matching | Client pays a round number; system suggests which invoices to apply it to | MEDIUM | Fuzzy matching by amount + client; manager confirms; reduces manual work |
| Advance payment (adiantamento do cliente) | Client pre-pays before invoice is issued | MEDIUM | `PaymentRecord` with `billing_document_id = null`; applied when invoice is created |
| Payment reminder workflow | Auto-send WhatsApp/email reminder when invoice is 7/14/30 days overdue | MEDIUM | ARQ cron; uses notification infrastructure |
| Bank reconciliation import | Import bank statement to match payments automatically | HIGH | Requires bank statement parsing (CSV/MT940); deferred to future milestone |

**Anti-features:**

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Automated payment collection (direct debit) | Eliminates chasing payments | No direct debit infrastructure in MZ for B2B; requires bank partnerships | Manual register + reminder workflow |
| Write-off / bad debt workflow | Write off uncollectable invoices | Requires accounting journal entries; tax implications | Mark invoice as `bad_debt` status only; no automatic P&L impact |
| Payment plan negotiation tracking | Track installment agreements | Adds complexity; edge case | Record each installment as a separate `PaymentRecord`; note in invoice |

---

### Category D: Client Statement and Aging (Extrato e Aging)

**Table stakes — must ship:**

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Client statement (extrato) | Running account balance for a single client; standard in B2B | MEDIUM | Query all invoices + payments for client; compute running balance |
| Aging buckets: current / 30 / 60 / 90+ days | Universal A/R analysis standard; expected by any accountant | MEDIUM | SQL CASE WHEN on `(today - due_date)` for unpaid invoices |
| Statement period filter | "Show me this client's account for Q1 2025" | LOW | Date range filter on statement query |
| Outstanding balance per client | Single number: total money owed by this client right now | LOW | `SUM(invoice.total_amount) - SUM(payments.amount)` where status != paid |
| Statement exportable (PDF / XLSX) | Sent to client for payment confirmation; auditor needs it | MEDIUM | Same export infrastructure as billing documents (fpdf2 + openpyxl) |

**Differentiators:**

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Statement auto-sent monthly | Automatically email/WhatsApp statement to client contact | MEDIUM | ARQ cron; requires notification infrastructure |
| Interest on overdue (juros de mora) | Contractual penalty for late payment; common in MZ B2B | MEDIUM | Configurable rate per client; computed field in statement; not an actual invoice line at MVP |
| Credit utilization indicator | Shows credit limit vs outstanding balance | LOW | Visual indicator in client detail: "MZN 45,000 of 100,000 limit used" |

**Anti-features:**

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Real-time balance push notifications | Notify manager when client pays | WebSocket infrastructure needed for real-time | Polling on A/R dashboard (60s refresh) is sufficient |
| Multi-currency client balance | Client paid in USD and MZN | FX conversion adds complexity; MZN rounding issues | Record payments in MZN only; manager converts before recording |
| Consolidated statement across tenants | If the same client is on multiple ROTAS tenants | Violates multitenant isolation model fundamentally | Each tenant manages its own client relationship |

---

### Category E: Accounts Receivable Dashboard

**Table stakes — must ship:**

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Total issued (total faturado) | How much was invoiced in the period | LOW | `SUM(total_amount)` on issued invoices |
| Total collected (total recebido) | How much cash came in | LOW | `SUM(PaymentRecord.amount)` in the period |
| Total outstanding (em aberto) | Money still owed | LOW | `total_issued - total_collected`; or direct from unpaid invoice sum |
| Aging summary table | All clients with overdue amounts, bucketed by days overdue | MEDIUM | One row per client; columns: current, 1–30, 31–60, 61–90, 90+ |
| Overdue invoice list | List of invoices past due_date that are not fully paid | LOW | Filter on `status != paid AND due_date < today`; ordered by days overdue DESC |
| Client with highest outstanding | Single KPI card: who owes the most right now | LOW | MAX of outstanding balance across clients |

**Differentiators:**

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| DSO (Days Sales Outstanding) metric | Standard treasury KPI: average days to collect | LOW | `DSO = (outstanding / total_invoiced_last_N_days) × N`; N=90 is standard |
| Collection forecast | Based on historical payment patterns, project cash inflows by week | HIGH | Requires payment history analysis; ML optional; deferred to future milestone |
| A/R trend chart (monthly) | Visualize outstanding balance over time | LOW | Simple line chart from monthly snapshots; already have data |
| Client risk score | Flag clients who consistently pay late | MEDIUM | Based on average payment delay vs terms; automated weekly recalculation |

**Anti-features:**

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Full accounting general ledger | Complete double-entry bookkeeping | Entirely different product category; adds enormous complexity | A/R module only; integrate with external accounting (Sage, QuickBooks export) |
| Tax reporting (IVA return) | Automatic VAT return preparation | Requires AT-certified software; complex tax rules | Export invoice data; let accountant file manually |
| Revenue recognition schedules | IFRS 15 / ASC 606 compliance | Enterprise-only concern; not relevant for SME transportadoras | Simple cash basis; not accrual |

---

### Feature Dependencies (Client Registry and A/R)

```
Client entity (CRUD, NUIT, payment terms)
    └──required by──> Contract migration (client_id FK)
    └──required by──> Invoice with client NUIT
    └──required by──> Payment registration (client_id on payment)
    └──required by──> Client statement
    └──required by──> A/R dashboard aging

Contract migration (client_name → client_id)
    └──required by──> Multi-contract invoicing (group by client)
    └──required by──> A/R dashboard (client-level aggregation)

Payment registration
    └──required by──> Client statement (running balance)
    └──required by──> Invoice status transitions (paid / partially_paid)
    └──required by──> A/R dashboard (total collected KPI)

Invoice sequential numbering
    └──required by──> PDF export with AT-compliant invoice number

Client statement + aging
    └──required by──> A/R dashboard (feeds aging summary table)

A/R dashboard
    └──enhances──> Client statement (provides fleet-wide view)
```

**Dependency notes:**

- Client entity must be built before anything else. Contract migration is a one-way Alembic migration; cannot be undone cleanly.
- Payment registration is independent of client entity technically (can reference `billing_document_id` without `client_id`), but the client-level balance aggregation requires `client_id` on payments.
- A/R dashboard is purely a read/aggregation layer; it can be built last once all source data exists.
- Invoice sequential numbering is low-complexity but must be atomic (PostgreSQL sequence, not application-level counter) to avoid gaps under concurrent requests.

---

### MVP Definition for Client Registry and A/R

**Launch with (this milestone):**
- [ ] Client entity: NUIT, legal_name, trade_name, billing address, payment terms, status
- [ ] Contract migration: backfill `client_id` from `client_name` (auto-create one client per unique name); preserve `client_name` as denormalized fallback for backwards compat
- [ ] Invoice sequential numbering: `invoice_number` field with PostgreSQL sequence
- [ ] Client NUIT on invoice PDF
- [ ] Payment registration: full amount, partial, method, reference, payment_date
- [ ] Invoice status machine: issued → partially_paid → paid → overdue (cron sets overdue)
- [ ] Client statement: list invoices + payments, running balance, period filter
- [ ] A/R dashboard: total issued, total collected, outstanding, aging buckets, overdue list

**Add after validation (v2.1):**
- [ ] Credit limit with soft warning (no hard enforcement at first)
- [ ] Multiple contacts per client
- [ ] Payment reminder via WhatsApp (after notification infrastructure is live)
- [ ] Statement PDF/XLSX export
- [ ] DSO metric

**Defer to future (v3+):**
- [ ] Client portal self-service login
- [ ] Credit note / invoice amendment
- [ ] Bank reconciliation import
- [ ] Collection forecast / risk scoring
- [ ] Interest on overdue computation

---

### Mozambique-Specific Constraints (Client Registry and A/R)

**NUIT format and validation (HIGH confidence):**
- 9 digits, all numeric: `^\d{9}$`
- First digit indicates entity type: 1=individual, 2=collective entity (companies), 3=public entities, 4=non-residents
- For B2B clients, NUIT starts with 4 (historically) or 2 (more recently issued)
- No public AT API for real-time NUIT validation — validate format only
- NUIT is mandatory on invoices per AT mandate effective May 2025 (verified via WebFetch)

**Invoice numbering (MEDIUM confidence):**
- AT (Autoridade Tributária) requires sequential invoice numbering with no gaps
- Format is not mandated by AT — `YYYY/NNNN` is common convention (e.g., `2025/0042`)
- Software used to issue invoices must be AT-certified for VAT-registered businesses
- ROTAS is issuing invoices on behalf of transportadoras, not for ROTAS's own revenue — the transportadora's accountant is responsible for AT filing; ROTAS just needs to produce correct numbering
- Implementation: PostgreSQL `SEQUENCE` per tenant, reset annually, format as `{year}/{seq:04d}`

**Payment terms in Mozambican logistics (MEDIUM confidence from web research):**
- Standard: Net 30 (pagamento a 30 dias)
- Common variants: Net 45, Net 60 for larger clients (mining, government)
- Government clients (ministries, state enterprises) often pay Net 90 or Net 120 in practice — despite contractual terms
- Cash-on-delivery exists for small operators but is not standard in B2B logistics
- Payment method: bank transfer dominates for amounts > 50,000 MZN; M-Pesa for smaller amounts

**MZN currency handling (HIGH confidence — already implemented in codebase):**
- All monetary columns use `Numeric(12, 2)` with `Decimal` type annotations (confirmed in billing models)
- No FX conversion needed for domestic clients — everything in MZN
- Display format: `MZN 45.000,00` (Portuguese locale: period as thousands separator, comma as decimal)
- Avoid float arithmetic — already resolved in Phase 4

---

### Implementation Sequence for Client Registry and A/R

Based on dependencies and risk:

1. **Client model + CRUD** — New `clients` table, NUIT validation, CRUD endpoints. No impact on existing billing.
2. **Contract migration** — Alembic migration: add `client_id` FK to `contracts`; backfill via auto-create. Keep `client_name` for backwards compat. Run migration with `NOT NULL` deferred until backfill is verified.
3. **Invoice sequential numbering** — Add `invoice_number` + `due_date` to `BillingDocument`. PostgreSQL sequence per tenant. Alembic migration.
4. **Multi-contract invoicing** — Modify `create_document` in `billing/service.py` to accept `client_id` instead of (or in addition to) `contract_id`. Group trips by client rather than contract.
5. **Payment registration** — New `payment_records` table. CRUD endpoints. Update invoice status machine.
6. **Client statement endpoint** — Read-only aggregation. No new tables needed.
7. **A/R dashboard endpoint** — Read-only aggregation. Aging SQL via CASE WHEN.
8. **PDF updates** — Add NUIT, invoice_number, due_date to billing PDF template.
9. **Manager UI** — Client list, client detail, A/R dashboard, payment registration form.

---

## Table Stakes vs Differentiators Summary

| Feature | Table Stakes | Differentiators |
|---|---|---|
| GPS Integration | Fleet map with last-known position (text + basic map), refresh every 60s | Real-time track, historical replay, geofencing, precise ETA |
| Driver Settlement | Advance issuance, expense recording, reconciliation calculation, settlement PDF | Multi-currency, per-expense dispute workflow, auto-import from fuel_logs |
| Customer Portal | Token-based shareable link, delivery status page (text only, no login) | Live map on tracking page, ETA updates, email/WhatsApp notifications |
| WhatsApp Notifications | Delivery confirmation to customer, document expiry alert to manager | Driver settlement notifications, ETA push, bidirectional communication |
| Self-Service Onboarding | Registration form, email verification, trial period, company wizard | Payment integration, free tier, in-app upgrade flow |
| Conflict Resolution | Sync status badge in driver PWA, manager conflict queue | Auto-resolution rules, driver detail view of conflicts |
| Tenant Limits | Hard limit enforcement at API level, 403 with clear error | Soft limit warnings, grace periods, import pre-check |
| Client Registry | NUIT, legal name, billing address, payment terms, status, contract FK migration | Credit limit, multiple contacts, client segmentation |
| Multi-Contract Invoicing | One invoice per client, sequential numbering, NUIT on PDF, due date | Proforma invoice, sub-totals by contract, credit note |
| Payment Registration | Full/partial payment, method, reference, value date, status transitions | Auto-matching, advance payment, payment reminders |
| Client Statement | Running balance, period filter, aging 30/60/90 | Auto-send monthly, interest on overdue, credit utilization |
| A/R Dashboard | Total issued/collected/outstanding, aging table, overdue list | DSO metric, collection forecast, risk score |

---

## Anti-Features for v2.0

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| TCP socket server for Teltonika Codec 8 | Requires separate infrastructure not supported by Railway/Render; binary protocol complexity; not MVP-feasible | HTTP webhook endpoint; configure devices to HTTP POST mode |
| Live GPS streaming via WebSocket | Sustaining WebSocket connections for a fleet of 20+ trucks on Railway is expensive; mobile clients drop connections | 60-second polling or SSE for fleet map; position stored server-side |
| Payroll integration in settlement | Overlaps with HR/payroll; different buyer; increases scope dramatically | Trip expense settlement only; export to XLSX for payroll system |
| Credit card required at trial start | Eliminates 80%+ of SME Mozambique signups; trust is low | No card at trial; manual invoice + bank transfer for first payment |
| Real-time conflict notification to driver | Drivers don't need real-time; creates anxiety; sync batch is async by design | Show count badge; notify when resolved; manager resolves in dashboard |
| In-app chat (driver ↔ manager) | WhatsApp is already open on driver's phone; in-app chat competes with a habit | Deep-link to WhatsApp; add manager phone number to key driver screens |
| Automatic FX rate fetching for settlement | No reliable free MZ-specific FX API; adds external dependency | Manager manually enters exchange rate at reconciliation time |
| AT NUIT validation via live API | No public AT API; would block client registration when API is unavailable | Format validation only (9-digit numeric) |
| Full accounting general ledger | Entirely different product; enormous scope | A/R module only; export for external accounting system |
| Auto credit hold enforcement | Can block operational trips mid-execution | Soft warning only; manual suspension by manager |
| Multi-currency client balance | FX conversion complexity; rounding issues | Record all payments in MZN; manager converts before entry |

---

## Feature Dependencies (Build Order)

```
WhatsApp notifications (infra)
  ← required by: customer portal (share link via WA), driver settlement (notifications), conflict resolution (driver notification)

ARQ worker (infra)
  ← required by: WhatsApp notifications, GPS geofencing, limit warning notifications, compliance check cron

GPS positions table + ingest endpoint
  ← required by: fleet map, geofencing, ETA, customer portal (map view)

Tenant limits enforcement (API layer)
  ← required by: self-service onboarding (plan tiers enforce limits)

Self-service onboarding
  ← required by: none (independent feature; needed for public SaaS launch)

Driver settlement
  ← required by: none (independent; enhances existing trip module)

Customer portal / tracking tokens
  ← optional dependency on GPS (map view); core status page works without GPS

Conflict resolution UI
  ← requires: server_version column on syncable entities (Alembic migration)
  ← requires: sync_conflicts table (new)
  ← requires: sync batch endpoint to return per-item status (AUTH-04)

[CLIENT REGISTRY AND A/R — current milestone]
Client entity (CRUD)
  ← required by: Contract migration
  ← required by: Multi-contract invoicing
  ← required by: Payment registration (client-level balance)
  ← required by: Client statement
  ← required by: A/R dashboard

Contract migration (client_id FK)
  ← required by: Multi-contract invoicing
  ← required by: A/R dashboard aging (aggregates by client)

Payment registration
  ← required by: Client statement running balance
  ← required by: Invoice status machine (paid / partially_paid)
  ← required by: A/R dashboard (total collected KPI)

Client statement + aging SQL
  ← required by: A/R dashboard (feeds aging summary)
```

**Recommended build order for current milestone:**
1. Client model + CRUD + NUIT validation (foundation for everything)
2. Contract migration backfill (unblocks invoice grouping)
3. Invoice sequential numbering + due date (AT compliance; low effort)
4. Multi-contract invoice creation (modify `create_document` to accept `client_id`)
5. Payment registration CRUD
6. Invoice status cron (set `overdue` when `due_date < today AND not paid`)
7. Client statement endpoint (read-only aggregation)
8. A/R dashboard endpoint (read-only aggregation)
9. PDF updates (NUIT, invoice_number, due_date)
10. Manager UI (client list, A/R dashboard, payment form)

---

## Gaps / Unknowns

1. **GPS device configuration access**: Operators may not have credentials to reconfigure their Teltonika/Coban devices from existing servers to ROTAS's endpoint. Some devices were configured by a third-party installer and credentials are lost. This is a field operations problem, not a software problem, but it blocks GPS integration entirely. **Needs customer validation before committing GPS integration to a milestone.**

2. **WhatsApp Business Account approval timeline**: Meta's business verification and phone number approval process has unpredictable timelines (1 day to 3 weeks). Template approval is separate and also variable. Starting this process must happen 4–6 weeks before planned launch. **This is a critical path item for any milestone that includes WhatsApp notifications.**

3. **Payment gateway for Mozambique**: No current-data confirmation of Flutterwave's live Mozambique integration as of 2025. Paystack does not operate in Mozambique (West Africa focus). **Needs verification before building automated billing. Manual invoice is the safe fallback.**

4. **Mozambique e-fatura compliance for SaaS invoices**: ROTAS issuing monthly subscription invoices to Mozambican companies must comply with AT (Autoridade Tributária) invoice numbering requirements. Whether digital invoices require AT registration is unclear. **Needs legal validation before billing goes live.**

5. **PostGIS availability on Railway/Render**: PostgreSQL on Railway supports extensions but PostGIS must be explicitly enabled. Confirm PostGIS is available before designing geofencing around it. **If unavailable: use bounding-box approximation (pure SQL, no extension required).**

6. **Driver WhatsApp number capture**: Current driver model may not have `phone_number` as a required field. Needs schema audit before building driver notifications. If the field exists but is optional, a migration to make it "encouraged" (not required but prominently prompted during driver creation) is needed.

7. **360dialog partnership for Mozambique**: 360dialog claims Africa coverage but per-country availability changes. Confirm Mozambique (+258) numbers are supported before committing to 360dialog as the BSP. Alternative: apply direct to Meta Cloud API (longer setup, lower ongoing cost).

8. **Contract backfill collision risk**: Multiple contracts may share the same `client_name` but represent different legal entities (e.g., two separate companies coincidentally named "Transportes do Sul"). Auto-creating one `Client` per unique `client_name` may merge distinct entities. **Backfill should create one client per unique `client_name` with a manual review step in the manager UI post-migration.**

9. **AT invoice certification for transportadoras**: Mozambique's AT mandate from May 2025 requires VAT-registered taxpayers to submit monthly invoice files. Whether ROTAS must be AT-certified software (as the tool generating invoices on behalf of transportadoras) is legally ambiguous. **ROTAS should consult an MZ tax attorney before the billing module goes live with client-facing invoices.**
