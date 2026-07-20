import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { loadEmployees } from "@/app/lib/hr-api";
import { EmployeeTableClient } from "./EmployeeTableClient";
import { Users } from "lucide-react";
import Link from "next/link";

export default async function HRPage() {
  await requireSession();
  
  const employees = await loadEmployees();
  
  const activeCount = employees.filter(e => e.status === "active").length;
  const payrollTotal = employees.filter(e => e.status === "active").reduce((acc, e) => acc + Number(e.base_salary), 0);

  return (
    <SidebarLayout active="recursos_humanos">
      <div className="w-full space-y-6">
        <div className="flex justify-between items-start">
          <PageHeader
            eyebrow="Recursos Humanos"
            title="Diretório de Colaboradores"
            description="Gestão centralizada de funcionários de todos os departamentos."
          />
          <Link href="/rh/processamento" className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold transition-colors mt-4 sm:mt-0">
            Processamento Salarial &rarr;
          </Link>
        </div>
        
        {/* Sumário */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-surface border border-border p-4 rounded-lg flex flex-col gap-1">
            <span className="text-xs uppercase font-semibold text-muted tracking-wider">Trabalhadores Ativos</span>
            <span className="text-2xl font-bold text-ink flex items-center gap-2">
              <Users className="text-blue-500" size={24} /> {activeCount}
            </span>
          </div>
          <div className="bg-surface border border-border p-4 rounded-lg flex flex-col gap-1">
            <span className="text-xs uppercase font-semibold text-muted tracking-wider">Massa Salarial Estimada Mensal</span>
            <span className="text-2xl font-bold text-ink">
              {payrollTotal.toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
            </span>
          </div>
        </div>

        <EmployeeTableClient initialEmployees={employees} />
      </div>
    </SidebarLayout>
  );
}
