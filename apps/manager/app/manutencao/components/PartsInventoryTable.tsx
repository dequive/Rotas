import { SparePart } from "@/app/lib/workshop-api";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
} from "@/app/components/ui/DataTable";
import { StatusBadge } from "@/app/components/ui/StatusBadge";

interface Props {
  parts: SparePart[];
}

function isLowStock(part: SparePart): boolean {
  return Number(part.current_quantity) <= Number(part.minimum_quantity);
}

export function PartsInventoryTable({ parts }: Props) {
  if (parts.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground" style={{ fontFamily: "Manrope, sans-serif" }}>
        Nenhuma peça registada no inventário.
      </div>
    );
  }

  return (
    <DataTable isEmpty={false}>
      <TableHeader>
        <TableRow>
          <RotasTableHeader>SKU</RotasTableHeader>
          <RotasTableHeader>Nome</RotasTableHeader>
          <RotasTableHeader>Stock Actual</RotasTableHeader>
          <RotasTableHeader>Mínimo</RotasTableHeader>
          <RotasTableHeader>Custo Médio</RotasTableHeader>
          <RotasTableHeader>Categoria</RotasTableHeader>
          <RotasTableHeader>Prateleira</RotasTableHeader>
          <RotasTableHeader>Estado</RotasTableHeader>
        </TableRow>
      </TableHeader>
      <TableBody>
        {parts.map((part) => (
          <RotasTableRow key={part.id}>
            <RotasTableCell className="font-mono text-sm tabular-nums">{part.sku}</RotasTableCell>
            <RotasTableCell>{part.name}</RotasTableCell>
            <RotasTableCell className="font-mono text-sm tabular-nums">
              {Number(part.current_quantity).toFixed(2)} {part.unit}
            </RotasTableCell>
            <RotasTableCell className="font-mono text-sm tabular-nums">
              {Number(part.minimum_quantity).toFixed(2)} {part.unit}
            </RotasTableCell>
            <RotasTableCell className="font-mono text-sm tabular-nums">
              {new Intl.NumberFormat("pt-MZ", {
                style: "currency",
                currency: "MZN",
                minimumFractionDigits: 2,
              }).format(Number(part.average_unit_cost))}
            </RotasTableCell>
            <RotasTableCell className="text-sm capitalize">
              {part.category ?? "—"}
            </RotasTableCell>
            <RotasTableCell className="font-mono text-sm">{part.shelf_location ?? "—"}</RotasTableCell>
            <RotasTableCell>
              {isLowStock(part) ? (
                <StatusBadge status="paragem" label="stock baixo" />
              ) : (
                <StatusBadge status="concluida" label="OK" />
              )}
            </RotasTableCell>
          </RotasTableRow>
        ))}
      </TableBody>
    </DataTable>
  );
}
