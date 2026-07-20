import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { fetchItems, fetchWarehouses } from "../lib/inventory-api";
import { ArmazemTableClient } from "./ArmazemTableClient";
import { Package } from "lucide-react";

export default async function ArmazemPage() {
  await requireSession();
  
  // Vamos buscar todo o inventário (Items) e Armazéns ao novo motor!
  const items = await fetchItems();
  const warehouses = await fetchWarehouses();

  const outOfStockCount = items.filter(p => Number(p.current_stock) === 0).length;
  // TODO: add minimum_stock to items if needed, for now hardcode logic
  const lowStockCount = items.filter(p => Number(p.current_stock) > 0 && Number(p.current_stock) <= 5).length;

  return (
    <SidebarLayout active="oficina">
      <div className="w-full space-y-6">
        <PageHeader
          eyebrow="Oficina & Manutenção"
          title="Armazém de Peças"
          description={`Catálogo com ${items.length} referências registadas.`}
        />
        
        {/* Sumário Rápido */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-surface border border-border p-4 rounded-lg flex flex-col gap-1">
            <span className="text-xs uppercase font-semibold text-muted tracking-wider">Total de Referências</span>
            <span className="text-2xl font-bold text-ink flex items-center gap-2">
              <Package className="text-blue-500" size={24} /> {items.length}
            </span>
          </div>
          <div className="bg-surface border border-border p-4 rounded-lg flex flex-col gap-1">
            <span className="text-xs uppercase font-semibold text-muted tracking-wider">Avisos de Stock Mínimo</span>
            <span className="text-2xl font-bold text-amber-600 flex items-center gap-2">
              {lowStockCount}
            </span>
          </div>
          <div className="bg-surface border border-border p-4 rounded-lg flex flex-col gap-1">
            <span className="text-xs uppercase font-semibold text-muted tracking-wider">Ruptura de Stock (Avarias Paradas)</span>
            <span className="text-2xl font-bold text-red-600 flex items-center gap-2">
              {outOfStockCount}
            </span>
          </div>
        </div>

        <ArmazemTableClient initialItems={items} warehouses={warehouses} />
      </div>
    </SidebarLayout>
  );
}
