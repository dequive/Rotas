import {
  Camera,
  CheckCircle2,
  FileText,
  LogOut,
  MapPin,
  ReceiptText,
  RefreshCw,
  Save,
  Truck,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { getAuth, bootstrap, type ActiveTrip, type ChecklistTemplate, clearAuth } from "./api";
import type { AuthState } from "./api";
import { db, makeLocalId, queueFuelLog, queueOperation, type SyncStatus } from "./db";
import { processSyncQueue } from "./sync";
import { PairingView } from "./views/PairingView";
import { TripStartView } from "./views/TripStartView";
import { LoadPermitView } from "./views/LoadPermitView";
import { CargoManifestView } from "./views/CargoManifestView";
import { TripStopView } from "./views/TripStopView";
import { DeliveryProofView } from "./views/DeliveryProofView";
import { useNetworkStatus } from "./hooks/useNetworkStatus";
import { useSyncStatus } from "./hooks/useSyncStatus";
import { SyncStatusBanner } from "./components/SyncStatusBanner";

type View =
  | "dashboard"
  | "checklist"
  | "fuel"
  | "load_permit"
  | "cargo_manifest"
  | "trip_stop"
  | "delivery_proof"
  | "new_trip";

type ChecklistResponseState = Record<string, { value: boolean; photo?: File }>;

type FuelFormState = {
  kmAtRefuel: string;
  liters: string;
  totalCost: string;
  stationName: string;
  paymentMethod: string;
  receiptPhoto?: File;
  odometerPhoto?: File;
};

const initialFuelForm: FuelFormState = {
  kmAtRefuel: "",
  liters: "",
  totalCost: "",
  stationName: "",
  paymentMethod: "mpesa",
};

function initialChecklistResponses(template: ChecklistTemplate): ChecklistResponseState {
  return Object.fromEntries(template.items.map((item) => [item.id, { value: true }]));
}

export function App() {
  const [auth, setAuth] = useState<AuthState | null>(getAuth);
  const [view, setView] = useState<View>("dashboard");
  const [activeTrip, setActiveTrip] = useState<ActiveTrip | null>(null);
  const [checklistTemplate, setChecklistTemplate] = useState<ChecklistTemplate | null>(null);
  const [checklistResponses, setChecklistResponses] = useState<ChecklistResponseState>({});
  const [fuelForm, setFuelForm] = useState<FuelFormState>(initialFuelForm);
  const [pendingCount, setPendingCount] = useState(0);
  const [lastMessage, setLastMessage] = useState("A carregar...");
  const [syncing, setSyncing] = useState(false);

  const { isOnline } = useNetworkStatus();
  const syncStatus = useSyncStatus(isOnline, syncing);

  useEffect(() => {
    if (!auth) return;
    void loadBootstrap();
    void refreshPendingCount();
  }, [auth]);

  async function loadBootstrap() {
    try {
      const data = await bootstrap();
      setActiveTrip(data.activeTrip);
      if (data.checklistTemplates[0]) {
        setChecklistTemplate(data.checklistTemplates[0]);
        setChecklistResponses(initialChecklistResponses(data.checklistTemplates[0]));
      }
      setLastMessage(data.activeTrip ? "Viagem activa carregada." : "Sem viagem activa.");
    } catch {
      setLastMessage("Sem rede — a trabalhar offline.");
    }
  }

  async function refreshPendingCount() {
    const count = await db.syncQueue.count();
    setPendingCount(count);
  }

  async function savePhoto(
    file: File | undefined,
    entityLocalId: string,
    entityType: "fuel_log" | "checklist",
    fileType: "receipt" | "photo",
    fieldKey?: string
  ) {
    if (!file) return undefined;
    const localId = makeLocalId(fileType);
    await db.photoQueue.add({
      localId,
      entityType,
      entityLocalId,
      fieldKey,
      blob: file,
      fileType,
      retryCount: 0,
      status: "local_only",
      createdAt: new Date().toISOString(),
    });
    return localId;
  }

  async function submitFuelLog(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth) return;
    const kmAtRefuel = Number(fuelForm.kmAtRefuel);
    const liters = Number(fuelForm.liters);
    const totalCost = Number(fuelForm.totalCost);
    if (!Number.isFinite(kmAtRefuel) || kmAtRefuel <= 0) {
      setLastMessage("Informe uma quilometragem válida.");
      return;
    }
    if (!Number.isFinite(liters) || liters <= 0) {
      setLastMessage("Informe os litros abastecidos.");
      return;
    }
    if (!Number.isFinite(totalCost) || totalCost < 0) {
      setLastMessage("Informe o valor pago.");
      return;
    }
    if (!activeTrip) {
      setLastMessage("Não há viagem activa. Crie uma viagem primeiro.");
      return;
    }

    const localId = makeLocalId("fuel_log");
    const receiptPhotoLocalId = await savePhoto(fuelForm.receiptPhoto, localId, "fuel_log", "receipt");
    const odometerPhotoLocalId = await savePhoto(fuelForm.odometerPhoto, localId, "fuel_log", "photo");

    await queueFuelLog({
      localId,
      vehicleId: activeTrip.vehicle_id,
      driverId: auth.driverId,
      stationName: fuelForm.stationName.trim() || undefined,
      fuelType: "gasoleo",
      liters,
      totalCost,
      kmAtRefuel,
      paymentMethod: fuelForm.paymentMethod || undefined,
      receiptPhotoLocalId,
      odometerPhotoLocalId,
    });

    setFuelForm(initialFuelForm);
    await refreshPendingCount();
    setLastMessage("Abastecimento guardado offline.");
    setView("dashboard");
  }

  async function submitChecklist() {
    if (!auth || !checklistTemplate || !activeTrip) {
      setLastMessage("Configure viatura, motorista e template antes do checklist.");
      return;
    }

    const missing = checklistTemplate.items.find((item) => {
      return item.requires_photo && !checklistResponses[item.id]?.photo;
    });
    if (missing) {
      setLastMessage(`Foto obrigatória em falta: ${missing.label}`);
      return;
    }

    const localId = makeLocalId("checklist");
    const responses: Record<string, { value: boolean; photoLocalId?: string }> = {};
    for (const item of checklistTemplate.items) {
      const response = checklistResponses[item.id] ?? { value: true };
      const photoLocalId = await savePhoto(response.photo, localId, "checklist", "photo", item.id);
      responses[item.id] = { value: response.value, photoLocalId };
    }

    await queueOperation({
      localId,
      operation: "create",
      entityType: "checklist",
      payload: {
        vehicleId: activeTrip.vehicle_id,
        driverId: auth.driverId,
        templateId: checklistTemplate.id,
        type: checklistTemplate.type,
        responses,
        complete: true,
        clientCapturedAt: new Date().toISOString(),
      },
    });

    setChecklistResponses(initialChecklistResponses(checklistTemplate));
    await refreshPendingCount();
    setLastMessage("Checklist guardado offline.");
    setView("dashboard");
  }

  async function syncNow() {
    if (!auth) return;
    setSyncing(true);
    setLastMessage("A sincronizar...");
    await processSyncQueue(auth.accessToken);
    await refreshPendingCount();
    setSyncing(false);
    setLastMessage("Sincronização concluída.");
  }

  function handleLogout() {
    clearAuth();
    setAuth(null);
    setActiveTrip(null);
  }

  if (!auth) {
    return <PairingView onPaired={(a) => setAuth(a)} />;
  }

  const tripId = activeTrip?.id ?? "local_trip";

  return (
    <main className="phone-shell">
      <header className="top">
        <div>
          <span>ROTAS Motorista</span>
          <h1>{auth.driverName}</h1>
        </div>
        <div className="header-actions">
          <button className="icon-btn" aria-label="Sincronizar" onClick={syncNow} disabled={syncing}>
            <RefreshCw size={20} className={syncing ? "spin" : ""} />
          </button>
          <button className="icon-btn" aria-label="Sair" onClick={handleLogout} title="Sair">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {activeTrip ? (
        <section className="status-card">
          <div>
            <p>Viagem activa</p>
            <strong>{activeTrip.origin} → {activeTrip.destination}</strong>
          </div>
          <span className={`status-badge ${activeTrip.billing_status}`}>
            {activeTrip.load_state ?? activeTrip.status}
          </span>
        </section>
      ) : (
        <section className="status-card status-card--empty">
          <p>Sem viagem activa</p>
          <button className="small-btn" onClick={() => setView("new_trip")}>
            <Truck size={14} /> Nova viagem
          </button>
        </section>
      )}

      {view === "dashboard" && (
        <section className="actions" aria-label="Acções da viagem">
          <button type="button" onClick={() => setView("checklist")} disabled={!checklistTemplate}>
            <CheckCircle2 />
            Checklist
          </button>
          <button type="button" onClick={() => setView("fuel")}>
            <ReceiptText />
            Combustível
          </button>
          <button type="button" onClick={() => setView("load_permit")}>
            <FileText />
            Load Permit
          </button>
          <button type="button" onClick={() => setView("cargo_manifest")}>
            <Truck />
            Manifesto
          </button>
          <button type="button" onClick={() => setView("delivery_proof")}>
            <Camera />
            Descarga
          </button>
          <button type="button" onClick={() => setView("trip_stop")}>
            <MapPin />
            Paragem
          </button>
        </section>
      )}

      {view === "new_trip" && (
        <TripStartView
          onTripCreated={(trip) => {
            setActiveTrip(trip);
            setView("dashboard");
            setLastMessage(`Viagem ${trip.origin} → ${trip.destination} criada.`);
          }}
        />
      )}

      {view === "checklist" && checklistTemplate && (
        <ChecklistPanel
          template={checklistTemplate}
          responses={checklistResponses}
          onChange={setChecklistResponses}
          onSubmit={submitChecklist}
          onBack={() => setView("dashboard")}
        />
      )}

      {view === "fuel" && (
        <FuelPanel
          form={fuelForm}
          onChange={setFuelForm}
          onSubmit={submitFuelLog}
          latestStatus={lastMessage}
          onBack={() => setView("dashboard")}
        />
      )}

      {view === "load_permit" && (
        <LoadPermitView
          tripLocalId={tripId}
          onSaved={() => { void refreshPendingCount(); setLastMessage("Load Permit guardado."); setView("dashboard"); }}
        />
      )}

      {view === "cargo_manifest" && (
        <CargoManifestView
          tripLocalId={tripId}
          onSaved={() => { void refreshPendingCount(); setLastMessage("Manifesto guardado."); setView("dashboard"); }}
        />
      )}

      {view === "trip_stop" && (
        <TripStopView
          tripLocalId={tripId}
          onSaved={() => { void refreshPendingCount(); setLastMessage("Paragem registada."); setView("dashboard"); }}
        />
      )}

      {view === "delivery_proof" && (
        <DeliveryProofView
          tripLocalId={tripId}
          onSaved={() => { void refreshPendingCount(); setLastMessage("Prova de entrega guardada."); setView("dashboard"); }}
        />
      )}

      {view === "dashboard" && <BillingPanel trip={activeTrip} />}

      <SyncStatusBanner status={syncStatus} />
    </main>
  );
}

// ── ChecklistPanel ──────────────────────────────────────────────

function ChecklistPanel({
  template,
  responses,
  onChange,
  onSubmit,
  onBack,
}: {
  template: ChecklistTemplate;
  responses: ChecklistResponseState;
  onChange: (r: ChecklistResponseState) => void;
  onSubmit: () => void;
  onBack: () => void;
}) {
  function setValue(itemId: string, value: boolean) {
    onChange({ ...responses, [itemId]: { ...(responses[itemId] ?? { value: true }), value } });
  }
  function setPhoto(itemId: string, photo: File | undefined) {
    onChange({ ...responses, [itemId]: { ...(responses[itemId] ?? { value: true }), photo } });
  }

  return (
    <section className="panel checklist-panel">
      <div className="panel-title">
        <h2>{template.name}</h2>
        <button className="back-btn" onClick={onBack}>← Voltar</button>
      </div>
      <div className="checklist-items">
        {template.items.map((item) => {
          const response = responses[item.id] ?? { value: true };
          return (
            <article className="checklist-item" key={item.id}>
              <div>
                <strong>{item.label}</strong>
                <span>
                  {item.is_blocking ? "Bloqueante" : "Verificação"}
                  {item.requires_photo ? " · foto obrigatória" : ""}
                </span>
              </div>
              <div className="segmented">
                <button className={response.value ? "selected" : ""} type="button" onClick={() => setValue(item.id, true)}>OK</button>
                <button className={!response.value ? "selected danger" : ""} type="button" onClick={() => setValue(item.id, false)}>Falha</button>
              </div>
              {item.requires_photo && (
                <label className="photo-field">
                  Foto
                  <input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(item.id, e.target.files?.[0])} />
                </label>
              )}
            </article>
          );
        })}
      </div>
      <button className="primary-action" type="button" onClick={onSubmit}>
        <Save size={18} /> Guardar checklist
      </button>
    </section>
  );
}

// ── FuelPanel ───────────────────────────────────────────────────

function FuelPanel({
  form,
  onChange,
  onSubmit,
  latestStatus,
  onBack,
}: {
  form: FuelFormState;
  onChange: (next: FuelFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  latestStatus: string;
  onBack: () => void;
}) {
  function update<K extends keyof FuelFormState>(key: K, value: FuelFormState[K]) {
    onChange({ ...form, [key]: value });
  }

  return (
    <section className="panel fuel-panel">
      <div className="panel-title">
        <h2>Abastecimento</h2>
        <button className="back-btn" onClick={onBack}>← Voltar</button>
      </div>
      <form className="fuel-form" onSubmit={onSubmit}>
        <label>Km actual<input inputMode="numeric" value={form.kmAtRefuel} onChange={(e) => update("kmAtRefuel", e.target.value)} placeholder="Ex: 45210" /></label>
        <label>Litros<input inputMode="decimal" value={form.liters} onChange={(e) => update("liters", e.target.value)} placeholder="Ex: 80" /></label>
        <label>Valor total<input inputMode="decimal" value={form.totalCost} onChange={(e) => update("totalCost", e.target.value)} placeholder="MZN" /></label>
        <label>Posto<input value={form.stationName} onChange={(e) => update("stationName", e.target.value)} placeholder="Nome do posto" /></label>
        <label>Pagamento
          <select value={form.paymentMethod} onChange={(e) => update("paymentMethod", e.target.value)}>
            <option value="mpesa">M-Pesa</option>
            <option value="emola">e-Mola</option>
            <option value="dinheiro">Dinheiro</option>
            <option value="cartao_frota">Cartão frota</option>
            <option value="vale">Vale</option>
          </select>
        </label>
        <label>Foto recibo<input type="file" accept="image/*" capture="environment" onChange={(e) => update("receiptPhoto", e.target.files?.[0])} /></label>
        <label>Foto odómetro<input type="file" accept="image/*" capture="environment" onChange={(e) => update("odometerPhoto", e.target.files?.[0])} /></label>
        <button className="primary-action" type="submit"><Save size={18} /> Guardar</button>
      </form>
      <p className={statusClassName(latestStatus)}>{latestStatus}</p>
    </section>
  );
}

// ── BillingPanel ────────────────────────────────────────────────

function BillingPanel({ trip }: { trip: ActiveTrip | null }) {
  if (!trip) return null;
  const steps = ["Carga", "Viagem", "Descarga", "Cobrança"];
  const doneIndex =
    trip.billing_status === "billed" ? 4 :
    trip.billing_status === "billable" ? 3 :
    trip.billing_status === "pending_delivery_validation" ? 2 :
    trip.billing_status === "pending_delivery_proof" ? 1 : 0;

  return (
    <section className="panel">
      <h2>Estado de cobrança</h2>
      <div className="progress">
        {steps.map((step, i) => (
          <span key={step} className={i < doneIndex ? "done" : ""}>{step}</span>
        ))}
      </div>
      <p className="billing-status-text">{
        trip.billing_status === "pending_delivery_proof" ? "Pendente: falta prova de descarga" :
        trip.billing_status === "pending_delivery_validation" ? "A aguardar validação da descarga" :
        trip.billing_status === "billable" ? "Pronto para cobrança" :
        trip.billing_status === "billed" ? "Cobrado" : trip.billing_status
      }</p>
    </section>
  );
}

function statusClassName(message: string) {
  const normalized = message.toLowerCase();
  const status: SyncStatus = normalized.includes("falhou") || normalized.includes("erro") ? "failed" : "local_only";
  return `form-status ${status}`;
}
