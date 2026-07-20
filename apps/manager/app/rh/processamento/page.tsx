import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { loadPayrollSlips } from "@/app/lib/hr-api";
import { PayrollTableClient } from "./PayrollTableClient";

export default async function PayrollPage({
  searchParams,
}: {
  searchParams: { month?: string; year?: string };
}) {
  await requireSession();
  
  const now = new Date();
  const month = searchParams.month ? parseInt(searchParams.month, 10) : now.getMonth() + 1;
  const year = searchParams.year ? parseInt(searchParams.year, 10) : now.getFullYear();

  const slips = await loadPayrollSlips(month, year);

  return (
    <SidebarLayout active="recursos_humanos">
      <div className="w-full space-y-6">
        <PageHeader
          eyebrow="Recursos Humanos"
          title="Processamento Salarial em Lote"
          description="Geração do Fecho Mensal e envio para a Contabilidade."
        />
        
        {/* Filtro de Mês e Ano */}
        <div className="flex gap-4 items-end">
          <form className="flex gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Mês</label>
              <select 
                name="month" 
                defaultValue={month}
                className="w-32 border border-border rounded-lg px-3 py-2 text-sm bg-surface"
              >
                {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                  <option key={m} value={m}>{new Date(2000, m - 1).toLocaleString('pt', { month: 'long' })}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Ano</label>
              <input 
                type="number" 
                name="year" 
                defaultValue={year} 
                className="w-24 border border-border rounded-lg px-3 py-2 text-sm bg-surface"
              />
            </div>
            <div className="pb-0.5">
              <button type="submit" className="px-4 py-2 bg-surface-2 border border-border rounded-lg text-sm font-semibold hover:bg-muted/20">
                Visualizar
              </button>
            </div>
          </form>
        </div>

        <PayrollTableClient initialSlips={slips} month={month} year={year} />
      </div>
    </SidebarLayout>
  );
}
