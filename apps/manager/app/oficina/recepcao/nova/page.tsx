"use client";

import { ArrowLeft, Camera, ClipboardCheck, Gauge, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { SidebarLayout } from "../../../components/SidebarLayout";
import { Button } from "../../../components/ui/Button";
import { PageHeader } from "../../../components/ui/PageHeader";
import { bffRequest } from "../../../lib/bff";
import { PhotoEvidenceUploader } from "../../components/PhotoEvidenceUploader";
import SignatureCanvas from "../../components/SignatureCanvas";
import VehicleHistoryPanel from "../../components/VehicleHistoryPanel";

interface VehicleOption {
  id: string;
  plate: string;
  brand: string;
  model: string;
  current_km: number;
}

interface ClientOption {
  id: string;
  trading_name: string;
  legal_name: string | null;
  phone: string | null;
  is_active: boolean;
}

const inputClass =
  "h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft";
const labelClass =
  "mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted";
const cardClass =
  "space-y-5 rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card sm:p-6";

async function readApiError(response: Response, fallback: string) {
  const body = (await response.json().catch(() => ({}))) as {
    detail?: string;
    error?: { message?: string };
  };
  return body.error?.message ?? body.detail ?? fallback;
}

export default function NewReceptionPage() {
  const router = useRouter();
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [ownershipType, setOwnershipType] = useState<"fleet" | "customer">(
    "customer",
  );
  const [selectedClientId, setSelectedClientId] = useState("");
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [odometerKm, setOdometerKm] = useState(0);
  const [deliveredByName, setDeliveredByName] = useState("");
  const [deliveredByPhone, setDeliveredByPhone] = useState("");
  const [pickupAuthorizedByName, setPickupAuthorizedByName] = useState("");
  const [pickupAuthorizedByPhone, setPickupAuthorizedByPhone] = useState("");
  const [reportedIssues, setReportedIssues] = useState("");
  const [visualCondition, setVisualCondition] = useState("");
  const [personalItems, setPersonalItems] = useState("");
  const [fuelLevel, setFuelLevel] = useState("half");
  const [estimatedCompletionAt, setEstimatedCompletionAt] = useState("");
  const [photoFileIds, setPhotoFileIds] = useState<string[]>([]);
  const [signatureFileId, setSignatureFileId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadOptions() {
      setLoadingOptions(true);
      setErrorMessage(null);
      try {
        const [vehiclesResponse, clientsResponse] = await Promise.all([
          fetch("/api/vehicles?limit=200", { cache: "no-store" }),
          fetch("/api/clients?limit=200", { cache: "no-store" }),
        ]);
        if (!vehiclesResponse.ok) {
          throw new Error(
            await readApiError(
              vehiclesResponse,
              "Não foi possível carregar as viaturas.",
            ),
          );
        }
        if (!clientsResponse.ok) {
          throw new Error(
            await readApiError(
              clientsResponse,
              "Não foi possível carregar os clientes.",
            ),
          );
        }
        const [vehicleData, clientData] = await Promise.all([
          vehiclesResponse.json() as Promise<VehicleOption[]>,
          clientsResponse.json() as Promise<ClientOption[]>,
        ]);
        if (active) {
          setVehicles(Array.isArray(vehicleData) ? vehicleData : []);
          setClients(
            Array.isArray(clientData)
              ? clientData.filter((client) => client.is_active)
              : [],
          );
        }
      } catch (err) {
        if (active) {
          setErrorMessage(
            err instanceof Error
              ? err.message
              : "Erro ao carregar os dados de referência.",
          );
        }
      } finally {
        if (active) setLoadingOptions(false);
      }
    }
    void loadOptions();
    return () => {
      active = false;
    };
  }, []);

  const selectedVehicle = useMemo(
    () => vehicles.find((vehicle) => vehicle.id === selectedVehicleId) ?? null,
    [selectedVehicleId, vehicles],
  );
  const isOdometerWarning =
    Boolean(selectedVehicle) &&
    odometerKm >= 0 &&
    odometerKm < (selectedVehicle?.current_km ?? 0);

  function handleVehicleChange(vehicleId: string) {
    setSelectedVehicleId(vehicleId);
    const vehicle = vehicles.find((item) => item.id === vehicleId);
    setOdometerKm(vehicle?.current_km ?? 0);
  }

  function handleClientChange(clientId: string) {
    setSelectedClientId(clientId);
    const client = clients.find((item) => item.id === clientId);
    if (!client) return;
    setDeliveredByName(client.trading_name);
    setDeliveredByPhone(client.phone ?? "");
    setPickupAuthorizedByName(client.trading_name);
    setPickupAuthorizedByPhone(client.phone ?? "");
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setErrorMessage(null);
    if (!selectedVehicleId) {
      setErrorMessage("Selecione uma viatura registada.");
      return;
    }
    if (ownershipType === "customer" && !selectedClientId) {
      setErrorMessage("Selecione o cliente proprietário da viatura.");
      return;
    }
    if (isOdometerWarning) {
      setErrorMessage(
        "O odómetro não pode ser inferior à leitura atual da viatura sem reconciliação prévia.",
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await bffRequest("/api/v1/workshop/receptions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          vehicle_id: selectedVehicleId,
          client_id:
            ownershipType === "customer" ? selectedClientId : undefined,
          odometer_at_reception: odometerKm,
          reported_issues: reportedIssues.trim() || undefined,
          visual_condition: visualCondition.trim() || undefined,
          personal_items: personalItems.trim() || undefined,
          fuel_level: fuelLevel,
          delivered_by_name: deliveredByName.trim() || undefined,
          delivered_by_phone: deliveredByPhone.trim() || undefined,
          pickup_authorized_by_name:
            pickupAuthorizedByName.trim() || undefined,
          pickup_authorized_by_phone:
            pickupAuthorizedByPhone.trim() || undefined,
          client_signature_file_id: signatureFileId || undefined,
          estimated_completion_at: estimatedCompletionAt
            ? new Date(estimatedCompletionAt).toISOString()
            : undefined,
        }),
      });
      if (!response.ok) {
        throw new Error(
          await readApiError(response, "Erro ao registar a receção da viatura."),
        );
      }
      const created = (await response.json()) as {
        id?: string;
        reception_number?: string;
      };
      if (!created.id) {
        throw new Error("A API não devolveu a identidade da nova receção.");
      }

      const evidenceResults = await Promise.all(
        photoFileIds.map(async (fileId, index) => {
          const photoResponse = await bffRequest(
            `/api/v1/workshop/receptions/${created.id}/photos`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "Idempotency-Key": crypto.randomUUID(),
              },
              body: JSON.stringify({
                file_id: fileId,
                caption: `Fotografia de entrada ${index + 1}`,
              }),
            },
          );
          return photoResponse.ok;
        }),
      );
      const failedEvidence = evidenceResults.filter((attached) => !attached).length;
      const warning =
        failedEvidence > 0 ? `?evidence_warning=${failedEvidence}` : "";
      router.push(`/oficina/recepcao/${created.id}${warning}`);
    } catch (err) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Erro de ligação ao registar a receção.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SidebarLayout active="recepcao">
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        <PageHeader
          eyebrow="Oficina Auto"
          title="Novo check-in"
          description="Registo operacional da entrada, intervenientes, condição e evidências da viatura."
          actions={
            <Button
              type="button"
              variant="outline"
              onClick={() => router.back()}
            >
              <ArrowLeft aria-hidden="true" className="h-4 w-4" />
              Cancelar
            </Button>
          }
        />

        {errorMessage && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
          >
            {errorMessage}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
          <form onSubmit={handleSubmit} className="space-y-6">
            <section className={cardClass}>
              <div className="flex items-center gap-2 border-b border-border pb-3">
                <ClipboardCheck
                  aria-hidden="true"
                  className="h-5 w-5 text-rotas-600"
                />
                <h2 className="text-base font-semibold text-ink">
                  Viatura e titular
                </h2>
              </div>

              <fieldset>
                <legend className={labelClass}>Origem da viatura</legend>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: "customer", label: "Cliente do tenant" },
                    { value: "fleet", label: "Frota própria" },
                  ].map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={ownershipType === option.value}
                      onClick={() => {
                        setOwnershipType(option.value as "fleet" | "customer");
                        if (option.value === "fleet") setSelectedClientId("");
                      }}
                      className={`min-h-11 rounded-[var(--r-md)] border px-3 py-2 text-sm font-semibold transition-colors ${
                        ownershipType === option.value
                          ? "border-rotas-500 bg-rotas-50 text-rotas-700 dark:bg-surface-2"
                          : "border-border bg-surface text-muted hover:bg-surface-2"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </fieldset>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="reception-vehicle" className={labelClass}>
                    Viatura *
                  </label>
                  <select
                    id="reception-vehicle"
                    required
                    disabled={loadingOptions}
                    value={selectedVehicleId}
                    onChange={(event) => handleVehicleChange(event.target.value)}
                    className={inputClass}
                  >
                    <option value="">
                      {loadingOptions ? "A carregar…" : "Selecione a viatura"}
                    </option>
                    {vehicles.map((vehicle) => (
                      <option key={vehicle.id} value={vehicle.id}>
                        {vehicle.plate} — {vehicle.brand} {vehicle.model}
                      </option>
                    ))}
                  </select>
                </div>

                {ownershipType === "customer" && (
                  <div>
                    <label htmlFor="reception-client" className={labelClass}>
                      Cliente *
                    </label>
                    <select
                      id="reception-client"
                      required
                      disabled={loadingOptions}
                      value={selectedClientId}
                      onChange={(event) => handleClientChange(event.target.value)}
                      className={inputClass}
                    >
                      <option value="">
                        {loadingOptions ? "A carregar…" : "Selecione o cliente"}
                      </option>
                      {clients.map((client) => (
                        <option key={client.id} value={client.id}>
                          {client.trading_name}
                          {client.legal_name ? ` — ${client.legal_name}` : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </section>

            <section className={cardClass}>
              <div className="flex items-center gap-2 border-b border-border pb-3">
                <UsersRound
                  aria-hidden="true"
                  className="h-5 w-5 text-rotas-600"
                />
                <h2 className="text-base font-semibold text-ink">
                  Entrega e levantamento autorizado
                </h2>
              </div>
              <p className="text-xs leading-relaxed text-muted">
                Confirme sempre as pessoas reais. A seleção do cliente apenas
                pré-preenche os contactos para reduzir digitação.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-4 rounded-[var(--r-md)] border border-border bg-surface-2 p-4">
                  <h3 className="text-sm font-semibold text-ink">Quem entrega</h3>
                  <div>
                    <label htmlFor="delivered-name" className={labelClass}>
                      Nome
                    </label>
                    <input
                      id="delivered-name"
                      value={deliveredByName}
                      onChange={(event) => setDeliveredByName(event.target.value)}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label htmlFor="delivered-phone" className={labelClass}>
                      Telefone
                    </label>
                    <input
                      id="delivered-phone"
                      type="tel"
                      value={deliveredByPhone}
                      onChange={(event) => setDeliveredByPhone(event.target.value)}
                      className={inputClass}
                    />
                  </div>
                </div>
                <div className="space-y-4 rounded-[var(--r-md)] border border-border bg-surface-2 p-4">
                  <h3 className="text-sm font-semibold text-ink">
                    Quem pode levantar
                  </h3>
                  <div>
                    <label htmlFor="pickup-name" className={labelClass}>
                      Nome
                    </label>
                    <input
                      id="pickup-name"
                      value={pickupAuthorizedByName}
                      onChange={(event) =>
                        setPickupAuthorizedByName(event.target.value)
                      }
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label htmlFor="pickup-phone" className={labelClass}>
                      Telefone
                    </label>
                    <input
                      id="pickup-phone"
                      type="tel"
                      value={pickupAuthorizedByPhone}
                      onChange={(event) =>
                        setPickupAuthorizedByPhone(event.target.value)
                      }
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>
            </section>

            <section className={cardClass}>
              <div className="flex items-center gap-2 border-b border-border pb-3">
                <Gauge
                  aria-hidden="true"
                  className="h-5 w-5 text-rotas-600"
                />
                <h2 className="text-base font-semibold text-ink">
                  Condição de entrada
                </h2>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="reception-odometer" className={labelClass}>
                    Odómetro (km) *
                  </label>
                  <input
                    id="reception-odometer"
                    required
                    type="number"
                    min={selectedVehicle?.current_km ?? 0}
                    value={odometerKm}
                    onChange={(event) => setOdometerKm(Number(event.target.value))}
                    className={`${inputClass} font-mono tabular-nums ${
                      isOdometerWarning
                        ? "border-status-awaiting bg-status-awaiting-soft"
                        : ""
                    }`}
                  />
                  {selectedVehicle && (
                    <p className="mt-1 text-xs text-muted">
                      Leitura atual:{" "}
                      <span className="font-mono tabular-nums">
                        {selectedVehicle.current_km.toLocaleString("pt-MZ")} km
                      </span>
                    </p>
                  )}
                </div>
                <div>
                  <label htmlFor="estimated-completion" className={labelClass}>
                    Conclusão estimada
                  </label>
                  <input
                    id="estimated-completion"
                    type="datetime-local"
                    value={estimatedCompletionAt}
                    onChange={(event) =>
                      setEstimatedCompletionAt(event.target.value)
                    }
                    className={inputClass}
                  />
                </div>
              </div>

              <fieldset>
                <legend className={labelClass}>Nível de combustível</legend>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                  {[
                    ["empty", "Reserva"],
                    ["quarter", "1/4"],
                    ["half", "1/2"],
                    ["three_quarter", "3/4"],
                    ["full", "Cheio"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={fuelLevel === value}
                      onClick={() => setFuelLevel(value)}
                      className={`min-h-11 rounded-[var(--r-md)] border px-2 text-xs font-semibold ${
                        fuelLevel === value
                          ? "border-rotas-500 bg-rotas-50 text-rotas-700 dark:bg-surface-2"
                          : "border-border bg-surface text-muted hover:bg-surface-2"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </fieldset>

              <div>
                <label htmlFor="reported-issues" className={labelClass}>
                  Sintomas ou avarias reportadas
                </label>
                <textarea
                  id="reported-issues"
                  rows={3}
                  value={reportedIssues}
                  onChange={(event) => setReportedIssues(event.target.value)}
                  className={`${inputClass} h-auto py-2`}
                />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="visual-condition" className={labelClass}>
                    Condição visual
                  </label>
                  <textarea
                    id="visual-condition"
                    rows={3}
                    value={visualCondition}
                    onChange={(event) => setVisualCondition(event.target.value)}
                    className={`${inputClass} h-auto py-2`}
                  />
                </div>
                <div>
                  <label htmlFor="personal-items" className={labelClass}>
                    Objetos pessoais
                  </label>
                  <textarea
                    id="personal-items"
                    rows={3}
                    value={personalItems}
                    onChange={(event) => setPersonalItems(event.target.value)}
                    className={`${inputClass} h-auto py-2`}
                  />
                </div>
              </div>
            </section>

            <section className={cardClass}>
              <div className="flex items-center gap-2 border-b border-border pb-3">
                <Camera
                  aria-hidden="true"
                  className="h-5 w-5 text-rotas-600"
                />
                <div>
                  <h2 className="text-base font-semibold text-ink">Evidências</h2>
                  <p className="mt-0.5 text-xs text-muted">
                    O hash é calculado pelo servidor; anexos confirmados não são
                    substituídos no histórico da receção.
                  </p>
                </div>
              </div>
              <PhotoEvidenceUploader
                label="Fotografias de entrada"
                onUpload={(photo) =>
                  setPhotoFileIds((current) => [...current, photo.id])
                }
                onRemove={(photoId) =>
                  setPhotoFileIds((current) =>
                    current.filter((id) => id !== photoId),
                  )
                }
              />
              <SignatureCanvas
                onSignatureCaptured={(fileId) => setSignatureFileId(fileId)}
                onSignatureCleared={() => setSignatureFileId(null)}
              />
            </section>

            <div className="flex justify-end border-t border-border pt-5">
              <Button
                type="submit"
                variant="accent"
                size="lg"
                loading={isSubmitting}
                disabled={loadingOptions || vehicles.length === 0}
              >
                <ClipboardCheck aria-hidden="true" className="h-5 w-5" />
                Confirmar check-in
              </Button>
            </div>
          </form>

          <aside>
            <VehicleHistoryPanel vehicleId={selectedVehicleId || null} />
          </aside>
        </div>
      </div>
    </SidebarLayout>
  );
}
