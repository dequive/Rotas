import { QrCode, Truck } from "lucide-react";
import Link from "next/link";
import { requireSession } from "../lib/auth";
import { loadVehicles } from "../lib/vehicles-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { VehicleFormModal } from "../components/VehicleFormModal";

const VEHICLE_DOCS: { key: string; short: string }[] = [
  { key: "insurance",            short: "SEG" },
  { key: "inspection",           short: "INS" },
  { key: "iav",                  short: "IAV" },
  { key: "sign_tax",             short: "LET" },
  { key: "cargo_book",           short: "CAD" },
  { key: "international_license", short: "INT" },
];

function docStatus(docs: Record<string, unknown> | null, key: string): "ok" | "expiring" | "missing" {
  if (!docs) return "missing";
  const validUntil = (docs[`${key}_valid_until`] ?? (docs[key] as Record<string, unknown> | null)?.valid_until) as string | null | undefined;
  if (!validUntil) return "missing";
  const days = Math.ceil((new Date(validUntil).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "missing";
  if (days <= 30) return "expiring";
  return "ok";
}

const DOC_COLORS = {
  ok:       "bg-success text-white",
  expiring: "bg-warning text-white",
  missing:  "bg-surface-2 text-muted border border-border",
} as const;

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  active: { label: "Activa", tone: "green" },
  maintenance: { label: "Manutenção", tone: "orange" },
  inactive: { label: "Inactiva", tone: "red" },
};

export default async function ViaturasPage() {
  await requireSession();
  const vehicles = await loadVehicles();

  return (
    <SidebarLayout active="viaturas">
      <div className="page-header">
        <div>
          <h1>Viaturas</h1>
          <p>{vehicles.length} viaturas registadas</p>
        </div>
        <VehicleFormModal />
      </div>

      <section className="panel">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Matrícula</th>
                <th>Marca / Modelo</th>
                <th>Ano</th>
                <th>Categoria</th>
                <th>Km actual</th>
                <th>Combustível</th>
                <th>Estado</th>
                <th>Documentos</th>
                <th>Acções</th>
                <th>Histórico</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-row">Sem viaturas registadas.</td>
                </tr>
              ) : (
                vehicles.map((v) => {
                  const meta = STATUS_LABEL[v.status] ?? { label: v.status, tone: "blue" };
                  return (
                    <tr key={v.id}>
                      <td>
                        <span className="plate">
                          <Truck size={14} />
                          {v.plate}
                        </span>
                      </td>
                      <td>
                        <strong>{v.brand}</strong>
                        <span className="muted-line">{v.model}</span>
                      </td>
                      <td>{v.year}</td>
                      <td>{v.category}</td>
                      <td>{v.current_km.toLocaleString("pt-MZ")} km</td>
                      <td>{v.fuel_type}</td>
                      <td>
                        <span className={`badge ${meta.tone}`}>{meta.label}</span>
                      </td>
                      <td>
                        <div className="flex items-center gap-1 flex-wrap">
                          {VEHICLE_DOCS.map(({ key, short }) => {
                            const st = docStatus(v.documents as Record<string, unknown> | null, key);
                            return (
                              <span
                                key={key}
                                title={`${key.replaceAll("_", " ")}: ${st === "ok" ? "válido" : st === "expiring" ? "a vencer" : "em falta"}`}
                                className={`inline-block text-[9px] font-bold px-1 py-0.5 rounded leading-none ${DOC_COLORS[st]}`}
                              >
                                {short}
                              </span>
                            );
                          })}
                        </div>
                      </td>
                      <td className="action-cell">
                        <VehicleFormModal vehicle={v} />
                        <a
                          href={`/api/v1/vehicles/${v.id}/qr-code`}
                          target="_blank"
                          className="icon-btn"
                          title="Ver QR Code"
                          rel="noreferrer"
                        >
                          <QrCode size={16} />
                        </a>
                      </td>
                      <td>
                        <Link
                          href={`/viaturas/${v.id}/historico`}
                          className="text-xs font-semibold"
                          style={{ color: "var(--blue)" }}
                        >
                          Ver Histórico
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </SidebarLayout>
  );
}
