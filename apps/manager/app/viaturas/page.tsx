import { QrCode, Truck } from "lucide-react";
import Link from "next/link";
import { requireSession } from "../lib/auth";
import { loadVehicles } from "../lib/vehicles-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { VehicleFormModal } from "../components/VehicleFormModal";
import { StatusBadge } from "../components/ui/StatusBadge";
import { PageHeader } from "../components/ui/PageHeader";

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
      <PageHeader
        eyebrow="Frota"
        title="Viaturas"
        description={`${vehicles.length} viaturas registadas`}
        actions={<VehicleFormModal />}
      />

      <section className="bg-surface border border-border rounded-lg p-4">
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
                  <td colSpan={9} className="text-muted text-center py-6">Sem viaturas registadas.</td>
                </tr>
              ) : (
                vehicles.map((v) => {
                  const meta = STATUS_LABEL[v.status] ?? { label: v.status, tone: "blue" };
                  return (
                    <tr key={v.id}>
                      <td>
                        <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                          <Truck size={14} />
                          {v.plate}
                        </span>
                      </td>
                      <td>
                        <strong>{v.brand}</strong>
                        <span className="block mt-0.5 text-muted text-xs">{v.model}</span>
                      </td>
                      <td>{v.year}</td>
                      <td>{v.category}</td>
                      <td>{v.current_km.toLocaleString("pt-MZ")} km</td>
                      <td>{v.fuel_type}</td>
                      <td>
                        <StatusBadge
                          status={v.status === "active" ? "activo" : v.status === "maintenance" ? "manutencao" : "inactivo"}
                          label={meta.label}
                        />
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
                      <td className="flex items-center gap-1.5 whitespace-nowrap">
                        <VehicleFormModal vehicle={v} />
                        <a
                          href={`/api/v1/vehicles/${v.id}/qr-code`}
                          target="_blank"
                          title="Ver QR Code"
                          rel="noreferrer"
                          className="inline-flex items-center justify-center h-8 w-8 rounded-md bg-surface text-ink-2 border border-border hover:bg-surface-2 hover:text-ink transition-colors duration-100 flex-shrink-0"
                        >
                          <QrCode size={16} />
                        </a>
                      </td>
                      <td>
                        <div className="flex flex-col gap-1">
                          <Link
                            href={`/viaturas/${v.id}`}
                            className="text-xs font-semibold text-amber"
                          >
                            Ver Detalhe
                          </Link>
                          <Link
                            href={`/viaturas/${v.id}/historico`}
                            className="text-xs font-semibold text-ink-2"
                          >
                            Ver Histórico
                          </Link>
                        </div>
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
