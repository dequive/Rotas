import { FileText } from "lucide-react";
import { requireSession } from "../lib/auth";
import { loadContracts } from "../lib/contracts-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { ContractFormModal } from "../components/ContractFormModal";

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  active: { label: "Activo", tone: "green" },
  inactive: { label: "Inactivo", tone: "red" },
  draft: { label: "Rascunho", tone: "blue" },
};

function formatDate(value: string | null) {
  if (!value) return "-";
  return value.slice(0, 10);
}

function formatMoney(value: number | null, currency: string) {
  if (value === null) return "-";
  return new Intl.NumberFormat("pt-MZ", { style: "currency", currency, maximumFractionDigits: 0 }).format(value);
}

export default async function ContratosPage() {
  await requireSession();
  const contracts = await loadContracts();

  return (
    <SidebarLayout active="contratos">
      <div className="page-header">
        <div>
          <h1>Contratos</h1>
          <p>{contracts.length} contratos registados</p>
        </div>
        <ContractFormModal />
      </div>

      <section className="panel">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Referência</th>
                <th>Cliente</th>
                <th>Título</th>
                <th>Preço unit.</th>
                <th>Inicia</th>
                <th>Termina</th>
                <th>Estado</th>
                <th>Acções</th>
              </tr>
            </thead>
            <tbody>
              {contracts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-row">Sem contratos registados.</td>
                </tr>
              ) : (
                contracts.map((c) => {
                  const meta = STATUS_LABEL[c.status] ?? { label: c.status, tone: "blue" };
                  return (
                    <tr key={c.id}>
                      <td>
                        <span className="plate">
                          <FileText size={14} />
                          {c.contract_reference}
                        </span>
                      </td>
                      <td>{c.client_name}</td>
                      <td>
                        <strong>{c.title}</strong>
                        <span className="muted-line">{c.service_type} · {c.billing_basis}</span>
                      </td>
                      <td>{formatMoney(c.default_unit_price, c.currency)}</td>
                      <td>{formatDate(c.starts_at)}</td>
                      <td>{formatDate(c.ends_at)}</td>
                      <td>
                        <span className={`badge ${meta.tone}`}>{meta.label}</span>
                      </td>
                      <td className="action-cell">
                        <ContractFormModal contract={c} />
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
