import { requireSession } from "@/app/lib/auth";
import { loadThirdParties } from "@/app/lib/third-party-api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { PageHeader } from "@/app/components/ui/PageHeader";
import Link from "next/link";
import { Building2 } from "lucide-react";

export default async function TerceirosPage({
  searchParams,
}: {
  searchParams: Promise<{ role_type?: string; status?: string; sector?: string; page?: string }>;
}) {
  await requireSession();
  const sp = await searchParams;
  const offset = (Number(sp.page ?? 1) - 1) * 50;
  const items = await loadThirdParties({
    status: sp.status,
    limit: 50,
    offset,
  }).catch(() => []);

  const selectCls = "h-9 px-2.5 border border-border-strong rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-2 focus:ring-amber/20 cursor-pointer";
  const labelCls = "text-[11px] font-semibold uppercase tracking-wide text-muted";

  return (
    <SidebarLayout active="terceiros">
      <div className="w-full space-y-6">
        <PageHeader
          eyebrow="Frota"
          title="Terceiros"
          description={`${items.length} terceiro${items.length !== 1 ? "s" : ""} registado${items.length !== 1 ? "s" : ""}`}
          actions={
            <Link href="/terceiros/novo" className="inline-flex items-center gap-1.5 h-[38px] px-[14px] text-sm font-bold rounded-lg bg-amber text-ink border border-amber hover:bg-amber-dark hover:border-amber-dark transition-colors duration-100 whitespace-nowrap">
              <Building2 size={15} />
              Novo Terceiro
            </Link>
          }
        />

        {/* Filter bar */}
        <form method="GET" className="bg-surface border border-border rounded-lg p-4 flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1">
            <label className={labelCls}>Tipo</label>
            <select name="role_type" defaultValue={sp.role_type ?? ""} className={`${selectCls} min-w-[140px]`}>
              <option value="">Todos</option>
              <option value="supplier">Fornecedor</option>
              <option value="service_provider">Prestador</option>
              <option value="client">Cliente</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Estado</label>
            <select name="status" defaultValue={sp.status ?? ""} className={`${selectCls} min-w-[120px]`}>
              <option value="">Todos</option>
              <option value="active">Activo</option>
              <option value="inactive">Inactivo</option>
              <option value="suspended">Suspenso</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Sector</label>
            <input
              name="sector"
              type="text"
              defaultValue={sp.sector ?? ""}
              placeholder="Filtrar sector..."
              className={`${selectCls} min-w-[160px]`}
            />
          </div>

          <button
            type="submit"
            className="h-9 px-3.5 border border-border-strong rounded-md bg-surface-2 text-ink text-[13px] font-semibold cursor-pointer hover:bg-surface transition-colors duration-100"
          >
            Filtrar
          </button>
        </form>

        {/* Table */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-collapse">
              <thead>
                <tr className="bg-surface-2 border-b border-border">
                  {["Nome", "Tipo", "Sector", "Estado", "Score médio", "Acções"].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-muted whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((tp) => (
                  <tr key={tp.id} className="border-b border-border">
                    <td className="px-4 py-3 font-semibold text-ink">
                      {tp.name}
                      {tp.trade_name && (
                        <span className="block text-[11px] font-normal text-muted mt-0.5">
                          {tp.trade_name}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {tp.roles?.map((r) => (
                          <span
                            key={r}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-surface-2 text-muted border border-border"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-muted flex-shrink-0" />
                            {r === "supplier"
                              ? "Fornecedor"
                              : r === "service_provider"
                                ? "Prestador"
                                : r === "client"
                                  ? "Cliente"
                                  : r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted">{tp.sector ?? "—"}</td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={
                          tp.status === "active"
                            ? "activo"
                            : tp.status === "suspended"
                              ? "pending"
                              : "inactivo"
                        }
                        label={
                          tp.status === "active"
                            ? "Activo"
                            : tp.status === "suspended"
                              ? "Suspenso"
                              : "Inactivo"
                        }
                      />
                    </td>
                    <td className="px-4 py-3 font-mono text-[13px] text-ink">
                      {tp.average_score ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/terceiros/${tp.id}`}
                        className="inline-flex px-2.5 py-1 rounded-md text-xs font-semibold text-ink bg-surface-2 border border-border no-underline hover:bg-surface transition-colors duration-100"
                      >
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-muted text-[13px]">
                      Nenhum terceiro encontrado
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
