import {
  BookOpen,
  Clock,
  DollarSign,
  Plus,
  Search,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";

export default async function WorkshopCatalogPage() {
  await requireSession();

  return (
    <SidebarLayout active="catalogo">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Catálogo de Serviços da Oficina
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Lista normalizada de serviços, preços base e tempos standard de mão de obra.
            </p>
          </div>
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
            <Plus className="h-4 w-4" /> Adicionar Serviço
          </button>
        </div>

        {/* Catalog Items Table Card */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Pesquisar código ou nome do serviço..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <select className="px-3 py-2 text-sm rounded-lg border border-input bg-background text-foreground">
              <option value="">Todas as Categorias</option>
              <option value="mecanica">Mecânica</option>
              <option value="electricidade">Electricidade</option>
              <option value="pintura">Pintura</option>
              <option value="pneus">Pneus</option>
              <option value="ac">Ar Condicionado</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">Código</th>
                  <th className="px-6 py-3">Nome do Serviço</th>
                  <th className="px-6 py-3">Categoria</th>
                  <th className="px-6 py-3">Duração Standard</th>
                  <th className="px-6 py-3 font-numeric text-right">Preço Base (MZN)</th>
                  <th className="px-6 py-3">Estado</th>
                  <th className="px-6 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">MOO-001</td>
                  <td className="px-6 py-4 font-medium text-foreground">Mudança de Óleo e Filtro</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-500 border border-blue-500/20">
                      Mecânica
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">45 minutos</td>
                  <td className="px-6 py-4 font-mono font-semibold text-foreground text-right">
                    2.500,00 MT
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      Ativo
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-xs font-medium text-primary hover:underline">
                      Editar
                    </button>
                  </td>
                </tr>

                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-medium text-foreground">ELE-004</td>
                  <td className="px-6 py-4 font-medium text-foreground">Diagnóstico Computadorizado Geral</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
                      Electricidade
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">60 minutos</td>
                  <td className="px-6 py-4 font-mono font-semibold text-foreground text-right">
                    1.800,00 MT
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      Ativo
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-xs font-medium text-primary hover:underline">
                      Editar
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
