import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Truck } from "lucide-react";

import { KpiCard } from "@/app/components/ui/KpiCard";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { EmptyState, EmptyStateInline } from "@/app/components/ui/EmptyState";
import { WorkQueue } from "@/app/components/ui/WorkQueue";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
} from "@/app/components/ui/DataTable";
import {
  Table,
  TableBody,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ─── KpiCard ─────────────────────────────────────────────────────────────────

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard label="Viagens Hoje" value="24" />);
    expect(screen.getByText("Viagens Hoje")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
  });

  it("renders loading skeleton when loading=true", () => {
    const { container } = render(<KpiCard label="KPI" value="0" loading />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    // Value should NOT be visible in skeleton state
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("renders up trend with correct arrow", () => {
    render(
      <KpiCard
        label="Eficiência"
        value="87%"
        trend={{ direction: "up", label: "+5% vs mês anterior" }}
      />
    );
    expect(screen.getByText("↑")).toBeInTheDocument();
    expect(screen.getByText("+5% vs mês anterior")).toBeInTheDocument();
  });

  it("renders down trend with correct arrow", () => {
    render(
      <KpiCard
        label="Custo"
        value="12.4"
        trend={{ direction: "down", label: "-2% vs mês anterior", positiveIsUp: false }}
      />
    );
    expect(screen.getByText("↓")).toBeInTheDocument();
  });

  it("renders neutral trend with dash", () => {
    render(
      <KpiCard
        label="Disponibilidade"
        value="100%"
        trend={{ direction: "neutral", label: "Sem alteração" }}
      />
    );
    expect(screen.getByText("–")).toBeInTheDocument();
  });

  it("renders without trend section when trend is undefined", () => {
    render(<KpiCard label="Total" value="0" />);
    expect(screen.queryByText("↑")).not.toBeInTheDocument();
    expect(screen.queryByText("↓")).not.toBeInTheDocument();
  });
});

// ─── StatusBadge — operational + billing states ──────────────────────────────

describe("StatusBadge", () => {
  const operationalStatuses = [
    { status: "em-rota", label: "Em rota" },
    { status: "concluida", label: "Concluída" },
    { status: "cancelada", label: "Cancelada" },
    { status: "planeada", label: "Planeada" },
    { status: "manutencao", label: "Em manutenção" },
    { status: "alerta", label: "Alerta" },
    { status: "paragem", label: "Paragem" },
  ] as const;

  operationalStatuses.forEach(({ status, label }) => {
    it(`renders "${status}" status correctly`, () => {
      render(<StatusBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  const billingStatuses = [
    { status: "billed", label: "Faturado" },
    { status: "billable", label: "A cobrar" },
    { status: "not_billable", label: "Não faturável" },
    { status: "waiver_required", label: "Necessita dispensa" },
    { status: "draft", label: "Rascunho" },
    { status: "issued", label: "Emitida" },
  ] as const;

  billingStatuses.forEach(({ status, label }) => {
    it(`renders billing status "${status}" → "${label}"`, () => {
      render(<StatusBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  const documentStatuses = [
    { status: "valid", label: "Válido" },
    { status: "expiring_soon", label: "A vencer" },
    { status: "expired", label: "Vencido" },
  ] as const;

  documentStatuses.forEach(({ status, label }) => {
    it(`renders document status "${status}" → "${label}"`, () => {
      render(<StatusBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("supports override label", () => {
    render(<StatusBadge status="concluida" label="Finalizado" />);
    expect(screen.getByText("Finalizado")).toBeInTheDocument();
    expect(screen.queryByText("Concluída")).not.toBeInTheDocument();
  });

  it("renders an unknown status as a readable fallback", () => {
    render(<StatusBadge status="estado_desconhecido" />);
    expect(screen.getByText("estado desconhecido")).toBeInTheDocument();
  });
});

// ─── EmptyState ──────────────────────────────────────────────────────────────

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState title="Sem viagens" />);
    expect(screen.getByText("Sem viagens")).toBeInTheDocument();
  });

  it("renders title and description", () => {
    render(
      <EmptyState
        title="Sem motoristas"
        description="Adicione um motorista para começar."
      />
    );
    expect(screen.getByText("Sem motoristas")).toBeInTheDocument();
    expect(
      screen.getByText("Adicione um motorista para começar.")
    ).toBeInTheDocument();
  });

  it("renders action when provided", () => {
    render(
      <EmptyState
        title="Sem viaturas"
        action={<button>Adicionar Viatura</button>}
      />
    );
    expect(
      screen.getByRole("button", { name: "Adicionar Viatura" })
    ).toBeInTheDocument();
  });

  it("does not render description when not provided", () => {
    render(<EmptyState title="Vazio" />);
    // No <p> with description content should exist beyond the title
    const paragraphs = screen.getAllByRole("paragraph").filter(
      (p) => p.textContent !== "Vazio"
    );
    expect(paragraphs).toHaveLength(0);
  });
});

describe("EmptyStateInline", () => {
  it("renders default label", () => {
    render(<EmptyStateInline />);
    expect(screen.getByText("Sem registos")).toBeInTheDocument();
  });

  it("renders custom label", () => {
    render(<EmptyStateInline label="Nenhum resultado" />);
    expect(screen.getByText("Nenhum resultado")).toBeInTheDocument();
  });
});

// ─── WorkQueue ───────────────────────────────────────────────────────────────

describe("WorkQueue", () => {
  const baseItems = [
    {
      id: "1",
      reference: "MT-001",
      title: "Revisão de 50.000 km",
      detail: "Mercedes Actros · Chapa XY-01-AB",
      meta: "Vence em 3 dias",
    },
    {
      id: "2",
      reference: "MT-002",
      title: "Troca de pneus",
      meta: "Urgente",
    },
  ];

  it("renders title and item count", () => {
    render(
      <WorkQueue
        icon={Truck}
        title="Manutenção Iminente"
        tone="orange"
        items={baseItems}
      />
    );
    expect(screen.getByText("Manutenção Iminente")).toBeInTheDocument();
    // item count badge
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders all items with reference and title", () => {
    render(
      <WorkQueue
        icon={Truck}
        title="Work Queue"
        tone="blue"
        items={baseItems}
      />
    );
    expect(screen.getByText("MT-001")).toBeInTheDocument();
    expect(screen.getByText("Revisão de 50.000 km")).toBeInTheDocument();
    expect(screen.getByText("MT-002")).toBeInTheDocument();
    expect(screen.getByText("Troca de pneus")).toBeInTheDocument();
  });

  it("renders detail and meta when provided", () => {
    render(
      <WorkQueue
        icon={Truck}
        title="Work Queue"
        tone="red"
        items={baseItems}
      />
    );
    expect(
      screen.getByText("Mercedes Actros · Chapa XY-01-AB")
    ).toBeInTheDocument();
    expect(screen.getByText("Vence em 3 dias")).toBeInTheDocument();
    expect(screen.getByText("Urgente")).toBeInTheDocument();
  });

  it("renders empty state when items is empty", () => {
    render(
      <WorkQueue
        icon={Truck}
        title="Alertas"
        tone="green"
        items={[]}
        emptyLabel="Tudo em ordem."
      />
    );
    expect(screen.getByText("Tudo em ordem.")).toBeInTheDocument();
    // count badge should be 0
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("renders default empty label when emptyLabel not provided", () => {
    render(<WorkQueue icon={Truck} title="Q" tone="amber" items={[]} />);
    expect(screen.getByText("Sem registos.")).toBeInTheDocument();
  });
});

// ─── DataTable ───────────────────────────────────────────────────────────────

describe("DataTable", () => {
  it("renders children inside a table", () => {
    render(
      <DataTable>
        <TableHeader>
          <TableRow>
            <RotasTableHeader>Placa</RotasTableHeader>
            <RotasTableHeader>Motorista</RotasTableHeader>
          </TableRow>
        </TableHeader>
        <TableBody>
          <RotasTableRow>
            <RotasTableCell>XY-01-AB</RotasTableCell>
            <RotasTableCell>João Silva</RotasTableCell>
          </RotasTableRow>
        </TableBody>
      </DataTable>
    );
    expect(screen.getByText("Placa")).toBeInTheDocument();
    expect(screen.getByText("Motorista")).toBeInTheDocument();
    expect(screen.getByText("XY-01-AB")).toBeInTheDocument();
    expect(screen.getByText("João Silva")).toBeInTheDocument();
  });

  it("renders EmptyStateInline when isEmpty=true", () => {
    render(
      <DataTable isEmpty emptyLabel="Sem viaturas registadas">
        <TableHeader>
          <TableRow>
            <RotasTableHeader>Col</RotasTableHeader>
          </TableRow>
        </TableHeader>
        <TableBody />
      </DataTable>
    );
    expect(screen.getByText("Sem viaturas registadas")).toBeInTheDocument();
  });

  it("does not render empty state when isEmpty=false", () => {
    render(
      <DataTable isEmpty={false} emptyLabel="Sem registos">
        <TableHeader>
          <TableRow>
            <RotasTableHeader>Col</RotasTableHeader>
          </TableRow>
        </TableHeader>
        <TableBody>
          <RotasTableRow>
            <RotasTableCell>Dado</RotasTableCell>
          </RotasTableRow>
        </TableBody>
      </DataTable>
    );
    expect(screen.queryByText("Sem registos")).not.toBeInTheDocument();
    expect(screen.getByText("Dado")).toBeInTheDocument();
  });
});
