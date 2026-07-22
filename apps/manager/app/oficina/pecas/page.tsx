import {
  AlertTriangle,
  ArrowDownCircle,
  Box,
  Package,
  Plus,
  RotateCcw,
  Search,
  TrendingDown,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";
import { loadSparePartsInventory, loadLowStockParts } from "../../lib/workshop-api";

export default async function WorkshopPartsPage() {
  await requireSession();

  const [parts, lowStock] = await Promise.all([
    loadSparePartsInventory(),
    loadLowStockParts(),
  ]);

  const totalParts = parts.length;
  const lowStockCount = lowStock.total;
  const totalStockValue = parts.reduce(
    (sum, p) => sum + p.current_quantity * p.average_unit_cost,
    0,
  );

  return (
    <SidebarLayout active="pecas-oficina">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Peças &amp; Inventário
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Gestão de stock de peças, requisições para OS e retoma de peças usadas.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-input bg-background hover:bg-accent transition-colors">
              <ArrowDownCircle className="h-4 w-4" /> Registar Entrada
            </button>
            <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              <Plus className="h-4 w-4" /> Nova Peça
            </button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Referências em Stock
              </span>
              <Package className="h-5 w-5 text-indigo-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">{totalParts}</div>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Alertas Rotura
              </span>
              <TrendingDown className="h-5 w-5 text-rose-500" />
            </div>
            <div className="text-2xl font-bold text-rose-600">{lowStockCount}</div>
            <p className="text-xs text-muted-foreground">Abaixo do mínimo definido</p>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Valor em Stock
              </span>
              <Box className="h-5 w-5 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {new Intl.NumberFormat("pt-MZ", {
                style: "decimal",
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              }).format(totalStockValue)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
          </div>
        </div>

        {/* Low Stock Alerts */}
        {lowStockCount > 0 && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 shadow-sm overflow-hidden">
            <div className="px-6 py-3 border-b border-amber-500/20 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-amber-600">
                Peças com Stock Abaixo do Mínimo ({lowStockCount})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-amber-500/5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-2.5">SKU</th>
                    <th className="px-6 py-2.5">Nome</th>
                    <th className="px-6 py-2.5 text-right">Actual</th>
                    <th className="px-6 py-2.5 text-right">Mínimo</th>
                    <th className="px-6 py-2.5">Fornecedor</th>
                    <th className="px-6 py-2.5 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {lowStock.items.slice(0, 5).map((item) => (
                    <tr key={item.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-3 font-mono text-foreground">{item.sku}</td>
                      <td className="px-6 py-3 text-foreground">{item.name}</td>
                      <td className="px-6 py-3 font-mono text-rose-600 text-right font-semibold">
                        {item.current_quantity}
                      </td>
                      <td className="px-6 py-3 font-mono text-muted-foreground text-right">
                        {item.minimum_quantity}
                      </td>
                      <td className="px-6 py-3 text-muted-foreground">
                        {item.supplier_name ?? "—"}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <button className="text-xs font-medium text-primary hover:underline">
                          Encomendar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Full Inventory Table */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold text-foreground">
              Inventário Completo
            </h2>
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Pesquisar por SKU, nome ou categoria..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">SKU</th>
                  <th className="px-6 py-3">Nome</th>
                  <th className="px-6 py-3">Categoria</th>
                  <th className="px-6 py-3">Localização</th>
                  <th className="px-6 py-3 text-right">Qtd</th>
                  <th className="px-6 py-3 text-right">Custo Unit. (MT)</th>
                  <th className="px-6 py-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {parts.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                      <Package className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                      <p className="text-sm">Nenhuma peça cadastrada.</p>
                    </td>
                  </tr>
                )}
                {parts.map((part) => {
                  const isLow = part.current_quantity <= part.minimum_quantity;
                  return (
                    <tr key={part.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-3 font-mono font-medium text-foreground">
                        {part.sku}
                      </td>
                      <td className="px-6 py-3 text-foreground">{part.name}</td>
                      <td className="px-6 py-3 text-muted-foreground">
                        {part.category ?? "—"}
                      </td>
                      <td className="px-6 py-3 text-muted-foreground font-mono text-xs">
                        {part.shelf_location ?? "—"}
                      </td>
                      <td
                        className={`px-6 py-3 font-mono text-right font-semibold ${
                          isLow ? "text-rose-600" : "text-foreground"
                        }`}
                      >
                        {part.current_quantity} {part.unit}
                      </td>
                      <td className="px-6 py-3 font-mono text-right text-muted-foreground">
                        {part.average_unit_cost.toFixed(2)}
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            isLow
                              ? "bg-rose-500/10 text-rose-500 border border-rose-500/20"
                              : "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                          }`}
                        >
                          {isLow ? "Stock Baixo" : "OK"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Core Return Section */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center gap-2">
            <RotateCcw className="h-4 w-4 text-cyan-500" />
            <h2 className="text-base font-semibold text-foreground">
              Retoma de Peças Usadas (Core Return)
            </h2>
          </div>
          <div className="px-6 py-8 text-center text-muted-foreground">
            <RotateCcw className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
            <p className="text-sm">
              Nenhuma retoma pendente. Peças substituídas com retoma aparecerão aqui.
            </p>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
