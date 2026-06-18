import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { loadClients } from "@/app/lib/clients-api";
import type { ClientResponse } from "@/app/lib/clients-api";
import { NovoClienteButton } from "./NovoClienteButton";
import { ClientsTable } from "./ClientsTable";

export default async function ClientesPage() {
  let clients: ClientResponse[] = [];
  try {
    clients = await loadClients();
  } catch {
    clients = [];
  }

  // KPI computations from list data
  const activeCount = clients.filter((c) => c.is_active).length;

  const totalOutstanding = clients.reduce(
    (sum, c) => sum + Number(c.outstanding_balance ?? 0),
    0
  );

  const exceededCount = clients.filter(
    (c) =>
      c.credit_limit &&
      Number(c.credit_limit) > 0 &&
      Number(c.outstanding_balance) > Number(c.credit_limit)
  ).length;

  function formatMzn(val: number): string {
    return `MZN ${val.toLocaleString("pt-MZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  return (
    <SidebarLayout active="clientes">
      <PageHeader
        title="Clientes"
        description={`${clients.length} clientes registados`}
        actions={<NovoClienteButton />}
      />

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Clientes Activos"
          value={String(activeCount)}
          semantic="default"
        />
        <KpiCard
          label="Saldo em Aberto"
          value={formatMzn(totalOutstanding)}
          semantic={totalOutstanding > 0 ? "error" : "default"}
        />
        <KpiCard
          label="Limite Excedido"
          value={String(exceededCount)}
          semantic={exceededCount > 0 ? "error" : "default"}
        />
        <KpiCard
          label="Contratos Activos"
          value="—"
          semantic="default"
        />
      </div>

      {/* Client table panel */}
      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <SectionHeader title="Lista de clientes" count={clients.length} />
        <div className="p-4">
          <ClientsTable clients={clients} />
        </div>
      </div>
    </SidebarLayout>
  );
}
