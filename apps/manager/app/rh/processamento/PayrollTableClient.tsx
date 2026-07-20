"use client";

import { useState } from "react";
import { PlayCircle, CheckCircle, Calculator, FileText, Printer, X } from "lucide-react";
import { PayrollSlip, generatePayroll } from "@/app/lib/hr-api";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { PayslipTemplate } from "./PayslipTemplate";

export function PayrollTableClient({ 
  initialSlips, 
  month, 
  year 
}: { 
  initialSlips: PayrollSlip[],
  month: number,
  year: number
}) {
  const [loading, setLoading] = useState(false);
  const [selectedSlip, setSelectedSlip] = useState<PayrollSlip | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      await generatePayroll(month, year);
      window.location.reload();
    } catch (err) {
      alert("Erro ao gerar processamento salarial.");
    } finally {
      setLoading(false);
    }
  };

  const totalNet = initialSlips.reduce((acc, slip) => acc + Number(slip.net_salary), 0);

  return (
    <div className="space-y-6">
      {/* Botões de Ação */}
      <div className="flex justify-between items-center bg-surface border border-border p-4 rounded-lg">
        <div>
          <h3 className="font-semibold text-lg text-ink">Folha de Vencimentos</h3>
          <p className="text-sm text-muted">Período: {month.toString().padStart(2, '0')} / {year}</p>
        </div>
        
        {initialSlips.length === 0 ? (
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            {loading ? "A Processar..." : <><Calculator size={18} /> Executar Fecho Salarial Mensal</>}
          </button>
        ) : (
          <div className="flex gap-3">
            <button
              disabled
              className="flex items-center gap-2 px-4 py-2 bg-surface-2 border border-border text-muted rounded-lg text-sm font-semibold cursor-not-allowed"
            >
              <CheckCircle size={18} /> Fecho Já Executado
            </button>
            <a 
              href={`/api/hr/payroll/export-ps2?month=${month}&year=${year}`}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold transition-colors"
            >
              <FileText size={18} /> Ficheiro Transferências (PS2)
            </a>
          </div>
        )}
      </div>

      {/* Tabela de Vencimentos */}
      {initialSlips.length > 0 && (
        <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs uppercase text-muted border-b border-border">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">ID Funcionário</th>
                  <th className="px-4 py-3 text-right font-semibold">Salário Ilíquido</th>
                  <th className="px-4 py-3 text-right font-semibold text-red-600">INSS (3%)</th>
                  <th className="px-4 py-3 text-right font-semibold text-red-600">IRPS</th>
                  <th className="px-4 py-3 text-right font-semibold text-red-600">Total Descontos</th>
                  <th className="px-4 py-3 text-right font-semibold">Líquido a Pagar</th>
                  <th className="px-4 py-3 text-center font-semibold">Acção</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {initialSlips.map((slip) => (
                  <tr key={slip.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-muted">{slip.employee_id.substring(0,8)}...</td>
                    <td className="px-4 py-3 text-right font-mono text-muted">
                      {Number(slip.gross_salary).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-red-600">
                      -{Number(slip.total_inss).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-red-600">
                      -{Number(slip.total_irps).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-red-600 font-bold">
                      -{Number(slip.total_deductions).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-ink text-lg">
                      {Number(slip.net_salary).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button 
                        onClick={() => setSelectedSlip(slip)}
                        className="text-blue-600 hover:text-blue-800 font-semibold text-xs flex items-center justify-center gap-1 mx-auto"
                      >
                        <Printer size={14} /> Ver Recibo A4
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-surface-2 border-t border-border">
                <tr>
                  <td colSpan={5} className="px-4 py-3 text-right font-semibold uppercase text-xs text-muted">Total Folha Salarial:</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-blue-600 text-xl">
                    {totalNet.toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
      
      {initialSlips.length === 0 && (
        <div className="text-center py-20 border border-dashed border-border rounded-lg bg-surface/50">
          <Calculator className="mx-auto text-muted mb-4" size={48} />
          <p className="text-muted font-medium">Os vencimentos deste mês ainda não foram processados.</p>
          <p className="text-sm text-muted/70 mt-1">Carregue no botão azul acima para executar o motor de salários.</p>
        </div>
      )}

      {/* MODAL DO RECIBO A4 */}
      {selectedSlip && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 overflow-y-auto p-4">
          <div className="relative bg-white w-full max-w-5xl overflow-hidden rounded-sm">
            <button 
              onClick={() => setSelectedSlip(null)} 
              className="absolute top-4 right-4 bg-black/50 hover:bg-black text-white p-2 rounded-full z-50 transition-colors"
            >
              <X size={24} />
            </button>
            <div className="max-h-[90vh] overflow-y-auto">
              <PayslipTemplate 
                slip={selectedSlip} 
                // We mock the employee data for the UI since we don't eager load the full Employee object in this endpoint
                employee={{
                  id: selectedSlip.employee_id,
                  tenant_id: selectedSlip.tenant_id,
                  first_name: "Funcionário",
                  last_name: selectedSlip.employee_id.substring(0,4),
                  employee_number: "01",
                  inss_beneficiary_number: "123456789",
                  nif_nuit: "100000000",
                  base_salary: Number(selectedSlip.gross_salary),
                  professional_category: "Colaborador",
                  role: "Role",
                  department: "Dep",
                  irps_tax_percentage: selectedSlip.lines.find(l => l.code === "D02")?.irps_tax_percentage || 0,
                  bank_account_nib: "",
                  date_of_birth: "",
                  hire_date: "",
                  termination_date: null,
                  status: "active",
                  driver_id: null,
                  user_id: null
                }} 
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
