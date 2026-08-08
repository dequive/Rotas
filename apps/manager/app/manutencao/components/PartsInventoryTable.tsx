"use client";

import type { Item, Warehouse } from "@/app/lib/inventory-api";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
  TableHeader,
  TableBody,
  TableRow,
} from "@/app/components/ui/DataTable";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { PartConsumptionModal } from "./PartConsumptionModal";

interface Props {
  parts: Item[];
  warehouses: Warehouse[];
  vehicles?: { id: string; plate: string }[];
}

function isLowStock(part: Item): boolean {
  return Number(part.current_stock) <= 5; // TODO: use real minimum_stock
}

export function PartsInventoryTable({ parts, warehouses, vehicles = [] }: Props) {
  if (parts.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        Nenhuma peça registada no inventário.
      </div>
    );
  }

  const formatMoney = (val: number) => {
    return new Intl.NumberFormat("pt-MZ", {
      style: "currency",
      currency: "MZN",
      minimumFractionDigits: 2,
    }).format(val);
  };

  return (
    <DataTable isEmpty={false}>
      <TableHeader>
        <TableRow>
          <RotasTableHeader>SKU</RotasTableHeader>
          <RotasTableHeader>Peça / Artigo</RotasTableHeader>
          <RotasTableHeader>Stock</RotasTableHeader>
          <RotasTableHeader>Custo Médio</RotasTableHeader>
          <RotasTableHeader>Valor em Stock</RotasTableHeader>
          <RotasTableHeader>Prateleira</RotasTableHeader>
          <RotasTableHeader>Estado</RotasTableHeader>
          <RotasTableHeader className="text-right">Ação Rápida</RotasTableHeader>
        </TableRow>
      </TableHeader>
      <TableBody>
        {parts.map((part) => {
          const qty = Number(part.current_stock);
          const cost = Number(part.average_unit_cost);
          const totalValue = qty * cost;

          return (
            <RotasTableRow key={part.id}>
              <RotasTableCell className="font-mono text-sm font-bold text-slate-700">{part.sku}</RotasTableCell>
              <RotasTableCell>
                <div className="font-bold text-slate-900">{part.name}</div>
                <div className="text-xs text-slate-500 capitalize">{part.category_id ?? "Geral"}</div>
              </RotasTableCell>
              <RotasTableCell className="font-mono text-sm">
                <span className={`px-2 py-0.5 rounded font-bold ${isLowStock(part) ? "bg-rose-100 text-rose-700" : "text-slate-700"}`}>
                  {qty.toFixed(2)} {part.unit_of_measure}
                </span>
              </RotasTableCell>
              <RotasTableCell className="font-mono text-sm text-slate-600">
                {formatMoney(cost)}
              </RotasTableCell>
              <RotasTableCell className="font-mono text-sm font-bold text-indigo-700">
                {formatMoney(totalValue)}
              </RotasTableCell>
              <RotasTableCell className="font-mono text-sm text-slate-500">—</RotasTableCell>
              <RotasTableCell>
                {isLowStock(part) ? (
                  <StatusBadge status="paragem" label="stock baixo" />
                ) : (
                  <StatusBadge status="concluida" label="OK" />
                )}
              </RotasTableCell>
              <RotasTableCell className="text-right">
                <PartConsumptionModal part={part} warehouses={warehouses} vehicles={vehicles} />
              </RotasTableCell>
            </RotasTableRow>
          );
        })}
      </TableBody>
    </DataTable>
  );
}
