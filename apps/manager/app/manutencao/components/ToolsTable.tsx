import { WorkshopToolItem } from "@/app/lib/workshop-api";
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
  tools: WorkshopToolItem[];
}

function isCalibrationNearExpiry(calibrationDueAt: string | null): boolean {
  if (!calibrationDueAt) return false;
  const dueDate = new Date(calibrationDueAt);
  const thirtyDaysFromNow = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  return dueDate <= thirtyDaysFromNow;
}

function formatDate(isoString: string | null): string {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleDateString("pt-MZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function ToolsTable({ tools }: Props) {
  if (tools.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground" style={{ fontFamily: "Manrope, sans-serif" }}>
        Nenhuma ferramenta registada.
      </div>
    );
  }

  return (
    <DataTable isEmpty={false}>
      <TableHeader>
        <TableRow>
          <RotasTableHeader>Código</RotasTableHeader>
          <RotasTableHeader>Nome</RotasTableHeader>
          <RotasTableHeader>Estado</RotasTableHeader>
          <RotasTableHeader>Calibração Próxima</RotasTableHeader>
          <RotasTableHeader>Localização</RotasTableHeader>
          <RotasTableHeader>Categoria</RotasTableHeader>
          <RotasTableHeader>Alerta</RotasTableHeader>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tools.map((tool) => {
          const nearExpiry = isCalibrationNearExpiry(tool.calibration_due_at);
          return (
            <RotasTableRow key={tool.id}>
              <RotasTableCell className="font-mono text-sm">{tool.code}</RotasTableCell>
              <RotasTableCell>{tool.name}</RotasTableCell>
              <RotasTableCell>
                <StatusBadge
                  status={tool.status === "available" ? "concluida" : "paragem"}
                  label={tool.status}
                />
              </RotasTableCell>
              <RotasTableCell className="font-mono text-sm tabular-nums">
                {formatDate(tool.calibration_due_at)}
              </RotasTableCell>
              <RotasTableCell className="text-sm">{tool.location ?? "—"}</RotasTableCell>
              <RotasTableCell className="text-sm capitalize">{tool.category ?? "—"}</RotasTableCell>
              <RotasTableCell>
                {nearExpiry ? (
                  <StatusBadge status="alerta" label="calibração vence" />
                ) : (
                  <span className="text-muted text-sm">—</span>
                )}
              </RotasTableCell>
            </RotasTableRow>
          );
        })}
      </TableBody>
    </DataTable>
  );
}
