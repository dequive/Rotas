import {
  CheckCircle2,
  Clock,
  FileText,
  Plus,
  Search,
  XCircle,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";

export default async function WorkshopQuotesPage() {
  await requireSession();

  return (
    <SidebarLayout active="orcamentos">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Orçamentos da Oficina
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Gestão de orçamentos iniciais e suplementares enviados aos clientes.
            </p>
          </div>
          <Link
            href="/oficina/orcamentos/novo"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" /> Criar Orçamento
          </Link>
        </div>

        {/* Quotes Table Card */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Pesquisar por nº orçamento, cliente ou matrícula..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <div className="flex items-center gap-2">
              <select className="px-3 py-2 text-sm rounded-lg border border-input bg-background text-foreground">
                <option value="">Todos os Estados</option>
                <option value="sent">Enviados</option>
                <option value="converted">Convertidos (OS)</option>
                <option value="rejected">Rejeitados</option>
                <option value="expired">Expirados</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">Nº Orçamento</th>
                  <th className="px-6 py-3">Viatura / Cliente</th>
                  <th className="px-6 py-3">Tipo</th>
                  <th className="px-6 py-3">Validade</th>
                  <th className="px-6 py-3 font-numeric text-right">Valor Total (MZN)</th>
                  <th className="px-6 py-3">Estado</th>
                  <th className="px-6 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">ORC-2026-0034</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Toyota Hilux (AFM-849-MC)</div>
                    <div className="text-xs text-muted-foreground">Manuel Silva Const.</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-500 border border-blue-500/20">
                      Inicial
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">28 Jul 2026</td>
                  <td className="px-6 py-4 font-mono font-semibold text-foreground text-right">
                    6.000,00 MT
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
                      <Clock className="h-3 w-3" /> Enviado
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button className="text-xs font-medium text-emerald-600 hover:underline">
                      Aceitar (OS)
                    </button>
                  </td>
                </tr>

                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">ORC-2026-0033</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Isuzu D-Max (AAG-102-MP)</div>
                    <div className="text-xs text-muted-foreground">Frota Própria</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-500/10 text-purple-500 border border-purple-500/20">
                      Suplementar (OS-2026-0044)
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">25 Jul 2026</td>
                  <td className="px-6 py-4 font-mono font-semibold text-foreground text-right">
                    2.400,00 MT
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      <CheckCircle2 className="h-3 w-3" /> Convertido
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-xs text-muted-foreground">OS Vinculada</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
