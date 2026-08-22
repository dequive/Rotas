import {
  Camera,
  CheckCircle2,
  LogOut,
  MapPin,
  ReceiptText,
  RefreshCw,
  Save,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  getAuth,
  bootstrap,
  type ActiveTrip,
  type BootstrapData,
  type ChecklistTemplate,
} from "./api";
import type { AuthState } from "./api";
import {
  db,
  getBootstrapCache,
  makeLocalId,
  queueFuelLog,
  queueOperation,
  saveBootstrapCache,
  getCurrentIdentityScope,
  type SyncStatus,
} from "./db";
import { processSyncQueue } from "./sync";
import { PairingView } from "./views/PairingView";
import { TripStopView } from "./views/TripStopView";
import { DeliveryProofView } from "./views/DeliveryProofView";
import { useNetworkStatus } from "./hooks/useNetworkStatus";
import { useSyncStatus } from "./hooks/useSyncStatus";
import { SyncStatusBanner } from "./components/SyncStatusBanner";
import { SyncIssuesPanel } from "./components/SyncIssuesPanel";
import { purgeDriverIdentity } from "./identity";

type View =
  | "dashboard"
  | "checklist"
  | "fuel"
  | "trip_stop"
  | "delivery_proof";

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
  const [logoutState, setLogoutState] = useState<
    "idle" | "purging" | "failed"
  >("idle");
  const syncLock = useRef(false);

  const { isOnline } = useNetworkStatus();
  const syncStatus = useSyncStatus(isOnline, syncing);

  useEffect(() => {
    if (!auth) return;
    void loadBootstrap();
    void refreshPendingCount();
  }, [auth]);

  useEffect(() => {
    if (!auth || !isOnline) return;
    void syncNow();
    const interval = window.setInterval(() => {
      void syncNow();
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [auth, isOnline]);

  function applyBootstrap(data: BootstrapData) {
    setActiveTrip(data.activeTrip);
    if (data.checklistTemplates[0]) {
      setChecklistTemplate(data.checklistTemplates[0]);
      setChecklistResponses(initialChecklistResponses(data.checklistTemplates[0]));
    } else {
      setChecklistTemplate(null);
      setChecklistResponses({});
    }
  }

  async function loadBootstrap() {
    if (!auth) return;
    try {
      const data = await bootstrap();
      applyBootstrap(data);
      await saveBootstrapCache(
        auth.tenantId,
        auth.driverId,
        auth.sessionId,
        data,
      );
      setLastMessage(data.activeTrip ? "Viagem activa carregada." : "Sem viagem activa.");
    } catch {
      const cached = await getBootstrapCache<BootstrapData>(
        auth.tenantId,
        auth.driverId,
        auth.sessionId,
      );
      if (cached) {
        applyBootstrap(cached.data);
        setLastMessage(
          `Modo offline — dados guardados em ${new Date(cached.cachedAt).toLocaleString("pt-MZ")}.`,
        );
      } else {
        setActiveTrip(null);
        setChecklistTemplate(null);
        setLastMessage("Sem rede e sem dados locais para este motorista.");
      }
    }
  }

  async function refreshPendingCount() {
    const scope = getCurrentIdentityScope();
    const count = scope
      ? await db.syncQueue
          .filter((item) =>
            item.tenantId === scope.tenantId &&
            item.driverId === scope.driverId &&
            item.sessionId === scope.sessionId
          )
          .count()
      : 0;
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
    const scope = getCurrentIdentityScope();
    if (!scope) throw new Error("driver_identity_scope_missing");
    const localId = makeLocalId(fileType);
    await db.photoQueue.add({
      ...scope,
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
      setLastMessage("Não há viagem atribuída. Contacte o gestor de frota.");
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
    if (!auth || syncLock.current || !isOnline) return;
    syncLock.current = true;
    setSyncing(true);
    setLastMessage("A sincronizar...");
    try {
      await processSyncQueue(auth.accessToken);
      await refreshPendingCount();
      setLastMessage("Sincronização concluída.");
    } catch {
      setLastMessage("Sincronização interrompida; os registos locais foram preservados.");
    } finally {
      syncLock.current = false;
      setSyncing(false);
    }
  }

  async function handleLogout() {
    setLogoutState("purging");
    setAuth(null);
    setActiveTrip(null);
    setChecklistTemplate(null);
    setChecklistResponses({});
    setFuelForm(initialFuelForm);
    setPendingCount(0);
    setView("dashboard");
    try {
      await purgeDriverIdentity();
      setLogoutState("idle");
    } catch {
      setLogoutState("failed");
    }
  }

  if (logoutState !== "idle") {
    return (
      <main className="phone-shell">
        <section className="panel identity-purge">
          <h1>Protecção da sessão</h1>
          {logoutState === "purging" ? (
            <p>A remover os dados locais do motorista anterior…</p>
          ) : (
            <>
              <p>
                Não foi possível confirmar a limpeza completa. O novo
                emparelhamento permanece bloqueado.
              </p>
              <button
                className="primary-action"
                type="button"
                onClick={() => void handleLogout()}
              >
                Tentar novamente
              </button>
            </>
          )}
        </section>
      </main>
    );
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
          <button className="icon-btn" aria-label="Sair" onClick={() => void handleLogout()} title="Sair">
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
          <span className={`status-badge ${activeTrip.status}`}>
            {activeTrip.load_state ?? activeTrip.status}
          </span>
        </section>
      ) : (
        <section className="status-card status-card--empty">
          <div>
            <p>Sem viagem atribuída</p>
            <strong>As novas viagens são atribuídas pelo gestor de frota.</strong>
          </div>
        </section>
      )}

      {view === "dashboard" && (
        <section className="actions" aria-label="Acções da viagem">
          <button type="button" onClick={() => setView("checklist")} disabled={!activeTrip || !checklistTemplate}>
            <CheckCircle2 />
            Checklist
          </button>
          <button type="button" onClick={() => setView("fuel")} disabled={!activeTrip}>
            <ReceiptText />
            Combustível
          </button>
          <button type="button" onClick={() => setView("delivery_proof")} disabled={!activeTrip}>
            <Camera />
            Descarga
          </button>
          <button type="button" onClick={() => setView("trip_stop")} disabled={!activeTrip}>
            <MapPin />
            Paragem
          </button>
        </section>
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

      {view === "dashboard" && syncStatus.errorCount > 0 && (
        <SyncIssuesPanel onChanged={() => void refreshPendingCount()} />
      )}

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

function statusClassName(message: string) {
  const normalized = message.toLowerCase();
  const status: SyncStatus = normalized.includes("falhou") || normalized.includes("erro") ? "failed" : "local_only";
  return `form-status ${status}`;
}
