import { FileText } from "lucide-react";
import { requireSession } from "../lib/auth";
import { loadContracts } from "../lib/contracts-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { ContractFormModal } from "../components/ContractFormModal";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  active: { label: "Activo", tone: "green" },
  inactive: { label: "Inactivo", tone: "red" },
  draft: { label: "Rascunho", tone: "blue" },
};

const SERVICE_TYPE_LABEL: Record<string, string> = {
  cargo_transport: "Transporte de carga",
  passenger_transport: "Transporte de passageiros",
  logistics: "Logística",
  courier: "Estafeta",
  tanker: "Cisterna",
  heavy_haul: "Carga pesada",
};

const BILLING_BASIS_LABEL: Record<string, string> = {
  per_trip: "Por viagem",
  per_km: "Por km",
  per_ton: "Por tonelada",
  per_hour: "Por hora",
  monthly: "Mensal",
  fixed: "Valor fixo",
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
      <PageHeader
        eyebrow="Financeiro"
        title="Contratos"
        description={`${contracts.length} contratos registados`}
        actions={<ContractFormModal />}
      />

      <section className="bg-surface border border-border rounded-lg p-4">
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
                  <td colSpan={8} className="text-muted text-center py-6">Sem contratos registados.</td>
                </tr>
              ) : (
                contracts.map((c) => {
                  const meta = STATUS_LABEL[c.status] ?? { label: c.status, tone: "blue" };
                  return (
                    <tr key={c.id}>
                      <td>
                        <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                          <FileText size={14} />
                          {c.contract_reference}
                        </span>
                      </td>
                      <td>{c.client_name}</td>
                      <td>
                        <strong>{c.title}</strong>
                        <span className="block mt-0.5 text-muted text-xs">
                          {SERVICE_TYPE_LABEL[c.service_type] ?? c.service_type}
                          {c.billing_basis ? ` · ${BILLING_BASIS_LABEL[c.billing_basis] ?? c.billing_basis}` : ""}
                        </span>
                      </td>
                      <td className="font-mono tabular-nums">{formatMoney(c.default_unit_price, c.currency)}</td>
                      <td>{formatDate(c.starts_at)}</td>
                      <td>{formatDate(c.ends_at)}</td>
                      <td>
                        <StatusBadge
                          status={c.status === "active" ? "activo" : c.status === "draft" ? "draft" : "inactivo"}
                          label={meta.label}
                        />
                      </td>
                      <td className="flex items-center gap-1.5 whitespace-nowrap">
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
