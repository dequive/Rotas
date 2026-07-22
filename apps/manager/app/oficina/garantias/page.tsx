import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Plus,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";

export default async function WorkshopWarrantiesPage() {
  await requireSession();

  return (
    <SidebarLayout active="garantias">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Garantias de Reparação
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Controlo de prazos e limites de quilometragem de garantias emitidas pela oficina.
            </p>
          </div>
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
            <Plus className="h-4 w-4" /> Emitir Garantia
          </button>
        </div>

        {/* Warranties Table Card */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Pesquisar por viatura, cliente ou OS..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <select className="px-3 py-2 text-sm rounded-lg border border-input bg-background text-foreground">
              <option value="">Todos os Estados</option>
              <option value="active">Ativas</option>
              <option value="claimed">Acionadas</option>
              <option value="expired">Expiradas</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">OS Origem</th>
                  <th className="px-6 py-3">Viatura / Cliente</th>
                  <th className="px-6 py-3">Tipo Garantia</th>
                  <th className="px-6 py-3">Prazo / Limite Km</th>
                  <th className="px-6 py-3">Estado</th>
                  <th className="px-6 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">OS-2026-0044</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Toyota Hilux (AFM-849-MC)</div>
                    <div className="text-xs text-muted-foreground">Manuel Silva Const.</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      Serviço Completo
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">
                    <div>6 Meses (Expira em 20 Jan 2027)</div>
                    <div className="text-xs font-mono">Limite: 55,000 km (Serviço a 50,000 km)</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      <ShieldCheck className="h-3 w-3" /> Ativa
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-xs font-medium text-amber-600 hover:underline">
                      Acionar Garantia
                    </button>
                  </td>
                </tr>

                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">OS-2026-0012</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Mitsubishi Canter (AAB-992-MC)</div>
                    <div className="text-xs text-muted-foreground">Transportes Maguezo</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-500 border border-blue-500/20">
                      Peças
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">
                    <div>12 Meses (Expira em 10 Fev 2027)</div>
                    <div className="text-xs font-mono">Limite: 150,000 km</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-500 border border-purple-500/20">
                      <AlertTriangle className="h-3 w-3" /> Acionada
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-xs text-muted-foreground">Em Análise</span>
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
