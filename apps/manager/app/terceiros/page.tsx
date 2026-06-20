import { requireSession } from "@/app/lib/auth";
import { loadThirdParties } from "@/app/lib/third-party-api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
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

  return (
    <SidebarLayout active="terceiros">
      <div className="w-full space-y-6">
        {/* Page header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: "Manrope, sans-serif" }}>
              Terceiros
            </h1>
            <p className="text-sm" style={{ color: "var(--muted)", marginTop: 2 }}>
              {items.length} terceiro{items.length !== 1 ? "s" : ""} registado{items.length !== 1 ? "s" : ""}
            </p>
          </div>
          <a
            href="/terceiros/novo"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 14px",
              background: "var(--amber)",
              color: "#fff",
              borderRadius: "var(--r-md, 6px)",
              fontSize: "13px",
              fontWeight: 600,
              fontFamily: "Manrope, sans-serif",
              textDecoration: "none",
              border: "none",
              cursor: "pointer",
            }}
          >
            <Building2 size={15} />
            Novo Terceiro
          </a>
        </div>

        {/* Filter bar */}
        <form
          method="GET"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg, 10px)",
            padding: "16px",
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "flex-end",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label
              style={{
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--muted)",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              Tipo
            </label>
            <select
              name="role_type"
              defaultValue={sp.role_type ?? ""}
              style={{
                padding: "6px 10px",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--r-md, 6px)",
                background: "var(--surface)",
                color: "var(--ink)",
                fontSize: "13px",
                fontFamily: "Manrope, sans-serif",
                minWidth: 140,
              }}
            >
              <option value="">Todos</option>
              <option value="supplier">Fornecedor</option>
              <option value="service_provider">Prestador</option>
              <option value="client">Cliente</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label
              style={{
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--muted)",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              Estado
            </label>
            <select
              name="status"
              defaultValue={sp.status ?? ""}
              style={{
                padding: "6px 10px",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--r-md, 6px)",
                background: "var(--surface)",
                color: "var(--ink)",
                fontSize: "13px",
                fontFamily: "Manrope, sans-serif",
                minWidth: 120,
              }}
            >
              <option value="">Todos</option>
              <option value="active">Activo</option>
              <option value="inactive">Inactivo</option>
              <option value="suspended">Suspenso</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label
              style={{
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--muted)",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              Sector
            </label>
            <input
              name="sector"
              type="text"
              defaultValue={sp.sector ?? ""}
              placeholder="Filtrar sector..."
              style={{
                padding: "6px 10px",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--r-md, 6px)",
                background: "var(--surface)",
                color: "var(--ink)",
                fontSize: "13px",
                fontFamily: "Manrope, sans-serif",
                minWidth: 160,
              }}
            />
          </div>

          <button
            type="submit"
            style={{
              padding: "7px 14px",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--r-md, 6px)",
              background: "var(--surface-2)",
              color: "var(--ink)",
              fontSize: "13px",
              fontWeight: 600,
              fontFamily: "Manrope, sans-serif",
              cursor: "pointer",
            }}
          >
            Filtrar
          </button>
        </form>

        {/* Table */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg, 10px)",
            overflow: "hidden",
          }}
        >
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "13px",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              <thead>
                <tr
                  style={{
                    background: "var(--surface-2)",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {["Nome", "Tipo", "Sector", "Estado", "Score médio", "Acções"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "10px 16px",
                        textAlign: "left",
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--muted)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((tp) => (
                  <tr
                    key={tp.id}
                    style={{ borderBottom: "1px solid var(--border)" }}
                  >
                    <td
                      style={{
                        padding: "12px 16px",
                        fontWeight: 600,
                        color: "var(--ink)",
                      }}
                    >
                      {tp.name}
                      {tp.trade_name && (
                        <span
                          style={{
                            display: "block",
                            fontSize: "11px",
                            fontWeight: 400,
                            color: "var(--muted)",
                            marginTop: 1,
                          }}
                        >
                          {tp.trade_name}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {tp.roles?.map((r) => (
                          <span
                            key={r}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              padding: "2px 8px",
                              borderRadius: 999,
                              fontSize: "11px",
                              fontWeight: 600,
                              background: "var(--surface-2)",
                              color: "var(--muted)",
                              border: "1px solid var(--border)",
                            }}
                          >
                            <span
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                background: "var(--muted)",
                                flexShrink: 0,
                              }}
                            />
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
                    <td
                      style={{
                        padding: "12px 16px",
                        color: "var(--muted)",
                        fontSize: "13px",
                      }}
                    >
                      {tp.sector ?? "—"}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
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
                    <td
                      style={{
                        padding: "12px 16px",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "13px",
                        color: "var(--ink)",
                      }}
                    >
                      {tp.average_score ?? "—"}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <Link
                        href={`/terceiros/${tp.id}`}
                        style={{
                          padding: "4px 10px",
                          borderRadius: "var(--r-md, 6px)",
                          fontSize: "12px",
                          fontWeight: 600,
                          fontFamily: "Manrope, sans-serif",
                          color: "var(--ink)",
                          background: "var(--surface-2)",
                          border: "1px solid var(--border)",
                          textDecoration: "none",
                          display: "inline-block",
                        }}
                      >
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      style={{
                        padding: "48px 16px",
                        textAlign: "center",
                        color: "var(--muted)",
                        fontSize: "13px",
                        fontFamily: "Manrope, sans-serif",
                      }}
                    >
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
