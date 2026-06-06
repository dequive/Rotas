import { Plus, QrCode, Truck } from "lucide-react";
import { requireSession } from "../lib/auth";
import { loadVehicles } from "../lib/vehicles-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { VehicleFormModal } from "../components/VehicleFormModal";

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
                <th>Acções</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-row">Sem viaturas registadas.</td>
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
