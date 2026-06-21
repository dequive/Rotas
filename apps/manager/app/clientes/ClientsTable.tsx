"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useState } from "react";
import type { ClientResponse } from "@/app/lib/clients-api";
import { IconButton } from "@/app/components/ui/IconButton";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
  RotasTableActionsCell,
  RotasTableActionsHeader,
  TableBody,
  TableHeader,
  TableRow,
} from "@/app/components/ui/DataTable";
import { MonoCell } from "@/app/components/ui/MonoCell";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { EmptyState } from "@/app/components/ui/EmptyState";
import { Users } from "lucide-react";
import { ClientFormModal } from "@/app/components/ClientFormModal";

interface ClientsTableProps {
  clients: ClientResponse[];
}

export function ClientsTable({ clients }: ClientsTableProps) {
  const [query, setQuery] = useState("");
  const [editClient, setEditClient] = useState<ClientResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  const filtered = query.trim()
    ? clients.filter((c) => {
        const q = query.toLowerCase();
        return (
          c.trading_name.toLowerCase().includes(q) ||
          (c.legal_name ?? "").toLowerCase().includes(q) ||
          c.nuit.includes(q) ||
          (c.city ?? "").toLowerCase().includes(q)
        );
      })
    : clients;

  function formatMzn(val: string | number | null | undefined): string {
    if (val == null || val === "") return "—";
    const n = Number(val);
    if (n === 0) return "Sem limite";
    return `MZN ${n.toLocaleString("pt-MZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  return (
    <>
      {/* Search */}
      <div className="mb-4 relative max-w-sm">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Pesquisar por nome, NUIT ou cidade…"
          className="w-full pl-8 pr-3 py-2 text-[13px] border border-border rounded-md bg-surface text-ink placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-amber/20 focus:border-amber"
        />
      </div>

      {filtered.length === 0 && query.trim() ? (
        <div className="py-8 text-center border border-border rounded-lg bg-surface">
          <p className="text-[13px] text-muted">
            Nenhum cliente encontrado para &quot;{query}&quot;
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Sem clientes registados"
          description="Crie o primeiro cliente para associar contratos e faturas."
        />
      ) : (
        <DataTable>
          <TableHeader>
            <TableRow>
              <RotasTableHeader>Cliente</RotasTableHeader>
              <RotasTableHeader>NUIT</RotasTableHeader>
              <RotasTableHeader>Cidade</RotasTableHeader>
              <RotasTableHeader>Prazo pgto.</RotasTableHeader>
              <RotasTableHeader>Limite de crédito</RotasTableHeader>
              <RotasTableHeader>Estado</RotasTableHeader>
              <RotasTableActionsHeader />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((c) => (
              <RotasTableRow key={c.id}>
                <RotasTableCell>
                  <div>
                    <span className="font-medium text-ink">{c.trading_name}</span>
                    {c.legal_name && (
                      <div className="text-[12px] text-muted leading-tight mt-0.5">
                        {c.legal_name}
                      </div>
                    )}
                  </div>
                </RotasTableCell>
                <RotasTableCell>
                  <MonoCell>{c.nuit}</MonoCell>
                </RotasTableCell>
                <RotasTableCell>{c.city ?? "—"}</RotasTableCell>
                <RotasTableCell>{c.payment_terms_days} dias</RotasTableCell>
                <RotasTableCell>
                  {c.credit_limit && Number(c.credit_limit) > 0 ? (
                    <MonoCell className="text-ink">
                      {formatMzn(c.credit_limit)}
                    </MonoCell>
                  ) : (
                    <span className="text-muted text-[13px]">Sem limite</span>
                  )}
                </RotasTableCell>
                <RotasTableCell>
                  <StatusBadge status={c.is_active ? "activo" : "inactivo"} />
                </RotasTableCell>
                <RotasTableActionsCell>
                  <Link
                    href={`/clientes/${c.id}`}
                    className="text-[12px] text-ink underline-offset-2 hover:underline px-2 py-1"
                  >
                    Ver
                  </Link>
                  <IconButton
                    label="Editar cliente"
                    className="w-auto px-2 text-[12px] font-semibold"
                    onClick={() => {
                      setEditClient(c);
                      setEditOpen(true);
                    }}
                  >
                    Editar
                  </IconButton>
                </RotasTableActionsCell>
              </RotasTableRow>
            ))}
          </TableBody>
        </DataTable>
      )}

      {/* Edit modal */}
      {editClient && (
        <ClientFormModal
          mode="edit"
          client={editClient}
          open={editOpen}
          onOpenChange={(o) => {
            setEditOpen(o);
            if (!o) setEditClient(null);
          }}
        />
      )}
    </>
  );
}
