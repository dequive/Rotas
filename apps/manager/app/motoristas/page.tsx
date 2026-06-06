import { User } from "lucide-react";
import { requireSession } from "../lib/auth";
import { loadDrivers } from "../lib/drivers-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { DriverFormModal } from "../components/DriverFormModal";
import { DriverScorecardPanel } from "../components/DriverScorecardPanel";
import { PairingCodeButton } from "../components/PairingCodeButton";

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
      <div className="page-header">
        <div>
          <h1>Motoristas</h1>
          <p>{drivers.length} motoristas registados</p>
        </div>
        <DriverFormModal />
      </div>

      <section className="panel">
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
                  <td colSpan={11} className="empty-row">Sem motoristas registados.</td>
                </tr>
              ) : (
                drivers.map((d) => {
                  const meta = STATUS_LABEL[d.status] ?? { label: d.status, tone: "blue" };
                  return (
                    <tr key={d.id}>
                      <td>
                        <span className="driver-name">
                          <User size={14} />
                          {d.full_name}
                        </span>
                      </td>
                      <td>{d.phone}</td>
                      <td>
                        <strong>{d.license_number}</strong>
                        <span className="muted-line">Cat. {d.license_category}</span>
                      </td>
                      <td>{formatDate(d.license_valid_until)}</td>
                      <td>{d.passport_number ?? <span className="muted-line">—</span>}</td>
                      <td>{d.passport_valid_until ? formatDate(d.passport_valid_until) : <span className="muted-line">—</span>}</td>
                      <td>{d.bi_number ?? <span className="muted-line">—</span>}</td>
                      <td>{d.bi_valid_until ? formatDate(d.bi_valid_until) : <span className="muted-line">—</span>}</td>
                      <td>
                        <span className={`badge ${d.score >= 80 ? "green" : d.score >= 50 ? "orange" : "red"}`}>
                          {d.score}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${meta.tone}`}>{meta.label}</span>
                      </td>
                      <td className="action-cell">
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
