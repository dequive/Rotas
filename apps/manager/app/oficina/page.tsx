import {
  BookOpen,
  CheckCircle2,
  Clock,
  FileText,
  Plus,
  ShieldCheck,
  Truck,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../components/SidebarLayout";
import { requireSession } from "../lib/auth";

export default async function WorkshopDashboardPage() {
  await requireSession();

  return (
    <SidebarLayout active="recepcao">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Gestão de Oficina Auto
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Controlo de recepção de viaturas, orçamentos, ordens de serviço e garantias multimarcas.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/oficina/orcamentos"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-input bg-background hover:bg-accent transition-colors"
            >
              <FileText className="h-4 w-4" /> Orçamentos
            </Link>
            <Link
              href="/oficina/recepcao/nova"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" /> Novo Check-in
            </Link>
          </div>
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Em Recepção
              </span>
              <Clock className="h-5 w-5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">4</div>
            <p className="text-xs text-muted-foreground">Aguardam diagnóstico ou orçamento</p>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Em Reparação
              </span>
              <Wrench className="h-5 w-5 text-indigo-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">7</div>
            <p className="text-xs text-muted-foreground">Com Ordem de Serviço em curso</p>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Prontas para Entrega
              </span>
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">3</div>
            <p className="text-xs text-muted-foreground">Serviço concluído com teste OK</p>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Garantias Ativas
              </span>
              <ShieldCheck className="h-5 w-5 text-blue-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">12</div>
            <p className="text-xs text-muted-foreground">Sob cobertura de tempo / km</p>
          </div>
        </div>

        {/* Active Workshop Receptions Board */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">
              Viaturas na Oficina (Check-ins Ativos)
            </h2>
            <span className="text-xs text-muted-foreground">Atualizado em tempo real</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">Nº Recepção</th>
                  <th className="px-6 py-3">Viatura / Cliente</th>
                  <th className="px-6 py-3">Avaria Reportada</th>
                  <th className="px-6 py-3">Odómetro Entrada</th>
                  <th className="px-6 py-3">Estado</th>
                  <th className="px-6 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">REC-2026-0012</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Toyota Hilux (AFM-849-MC)</div>
                    <div className="text-xs text-muted-foreground">Manuel Silva Const.</div>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground max-w-xs truncate">
                    Ruído intenso nos travões dianteiros e fuga ligeira de óleo
                  </td>
                  <td className="px-6 py-4 font-mono text-muted-foreground">45,210 km</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
                      Em Diagnóstico
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <Link
                      href="/oficina/orcamentos/novo?reception_id=REC-2026-0012"
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      Orçar
                    </Link>
                  </td>
                </tr>

                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">REC-2026-0011</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Isuzu D-Max (AAG-102-MP)</div>
                    <div className="text-xs text-muted-foreground">Frota Própria (TMS)</div>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground max-w-xs truncate">
                    Revisão dos 60.000 km e mudança de pastilhas
                  </td>
                  <td className="px-6 py-4 font-mono text-muted-foreground">60,040 km</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                      Em Serviço (OS-2026-0044)
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <Link
                      href="/oficina/os"
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      Ver OS
                    </Link>
                  </td>
                </tr>

                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">REC-2026-0010</td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-foreground">Mitsubishi Canter (AAB-992-MC)</div>
                    <div className="text-xs text-muted-foreground">Transportes Maguezo Lda</div>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground max-w-xs truncate">
                    Substituição de embraiagem e rectificação de discos
                  </td>
                  <td className="px-6 py-4 font-mono text-muted-foreground">128,400 km</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      Pronta para Levantamento
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button className="text-xs font-medium text-emerald-600 hover:underline">
                      Registar Entrega
                    </button>
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
