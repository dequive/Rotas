import { User } from "lucide-react";
import Link from "next/link";
import { requireSession } from "../lib/auth";
import { loadDrivers } from "../lib/drivers-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { DriverFormModal } from "../components/DriverFormModal";
import { DriverScorecardPanel } from "../components/DriverScorecardPanel";
import { PairingCodeButton } from "../components/PairingCodeButton";
import { DriverHubButton } from "../components/DriverHubButton";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  active: { label: "Activo", tone: "green" },
  inactive: { label: "Inactivo", tone: "red" },
  suspended: { label: "Suspenso", tone: "orange" },
};

function formatDate(value: string | null) {
  if (!value) return "-";
  return value.slice(0, 10);
}

export default async function MotoristasPage() {
  await requireSession();
  const drivers = await loadDrivers();

  return (
    <SidebarLayout active="motoristas">
      <PageHeader
        eyebrow="Frota"
        title="Motoristas"
        description={`${drivers.length} motoristas registados`}
        actions={<DriverFormModal />}
      />

      <section className="bg-surface border border-border rounded-lg p-4">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Telefone</th>
                <th>Carta de Condução</th>
                <th>Validade carta</th>
                <th>Passaporte</th>
                <th>Val. passaporte</th>
                <th>B.I.</th>
                <th>Val. B.I.</th>
                <th>Score</th>
                <th>Estado</th>
                <th>Acções</th>
              </tr>
            </thead>
            <tbody>
              {drivers.length === 0 ? (
                <tr>
                  <td colSpan={11} className="text-muted text-center py-6">Sem motoristas registados.</td>
                </tr>
              ) : (
                drivers.map((d) => {
                  const meta = STATUS_LABEL[d.status] ?? { label: d.status, tone: "blue" };
                  return (
                    <tr key={d.id}>
                      <td>
                        <DriverHubButton driverId={d.id} driverName={d.full_name} />
                      </td>
                      <td>{d.phone}</td>
                      <td>
                        <strong>{d.license_number}</strong>
                        <span className="block mt-0.5 text-muted text-xs">Cat. {d.license_category}</span>
                      </td>
                      <td>{formatDate(d.license_valid_until)}</td>
                      <td>{d.passport_number ?? <span className="block mt-0.5 text-muted text-xs">—</span>}</td>
                      <td>{d.passport_valid_until ? formatDate(d.passport_valid_until) : <span className="block mt-0.5 text-muted text-xs">—</span>}</td>
                      <td>{d.bi_number ?? <span className="block mt-0.5 text-muted text-xs">—</span>}</td>
                      <td>{d.bi_valid_until ? formatDate(d.bi_valid_until) : <span className="block mt-0.5 text-muted text-xs">—</span>}</td>
                      <td>
                        <StatusBadge
                          status={d.score >= 80 ? "concluida" : d.score >= 50 ? "pending" : "alerta"}
                          label={String(d.score)}
                        />
                      </td>
                      <td>
                        <StatusBadge
                          status={d.status === "active" ? "activo" : d.status === "suspended" ? "pending" : "inactivo"}
                          label={meta.label}
                        />
                      </td>
                      <td className="flex items-center gap-1.5 whitespace-nowrap">
                        <DriverFormModal driver={d} />
                        <PairingCodeButton driverId={d.id} driverName={d.full_name} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
      <DriverScorecardPanel drivers={drivers.map((d) => ({ id: d.id, full_name: d.full_name }))} />
    </SidebarLayout>
  );
}
