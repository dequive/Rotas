import React from "react";
import type { PayrollSlip, Employee } from "@/app/lib/hr-api";

export function PayslipTemplate({ slip, employee }: { slip: PayrollSlip, employee: Employee }) {
  
  // O componente interno desenha uma "via" (Original ou Duplicado)
  const PayslipHalf = ({ type }: { type: "ORIGINAL" | "DUPLICADO" }) => (
    <div className="w-full sm:w-1/2 bg-white text-black p-4 flex flex-col text-[10px] sm:text-xs font-sans leading-tight border-r border-dashed border-gray-400 last:border-none relative h-full min-h-[800px]">
      
      {/* CABEÇALHO DA EMPRESA E TIPO DE VIA */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-bold text-sm">Zohra Group SA</h2>
          <p>EN7, Bairro Mpadwe</p>
          <p>Tete</p>
          <p className="mt-2">NUIT: 400323453</p>
        </div>
        <div className="text-right">
          <span className="uppercase">{type}</span>
        </div>
      </div>
      
      {/* DATA DE PROCESSAMENTO */}
      <div className="text-right font-semibold mb-1">
        Processamento de {new Date(slip.period_year, slip.period_month - 1).toLocaleString('pt', { month: 'long' })} de {slip.period_year}
      </div>

      {/* DADOS DO TRABALHADOR - LINHA 1 (Verde Ciano) */}
      <table className="w-full border-collapse border border-black mb-2">
        <tbody>
          <tr className="bg-[#00FFFF]">
            <td colSpan={5} className="border border-black font-bold px-1 py-0.5">Nome</td>
          </tr>
          <tr>
            <td colSpan={5} className="border border-black px-1 py-0.5">{employee.first_name} {employee.last_name}</td>
          </tr>
          <tr className="bg-[#00FFFF] text-center font-semibold">
            <td className="border border-black px-1 py-0.5">Nº Empregado</td>
            <td className="border border-black px-1 py-0.5">Nº Beneficiário</td>
            <td className="border border-black px-1 py-0.5">Nº Contribuinte</td>
            <td className="border border-black px-1 py-0.5">Valor Dia</td>
            <td className="border border-black px-1 py-0.5">Salário Base</td>
          </tr>
          <tr className="text-center">
            <td className="border border-black px-1 py-0.5">{employee.employee_number || "---"}</td>
            <td className="border border-black px-1 py-0.5">{employee.inss_beneficiary_number || "---"}</td>
            <td className="border border-black px-1 py-0.5">{employee.nif_nuit || "---"}</td>
            <td className="border border-black px-1 py-0.5">{(employee.base_salary / 30).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            <td className="border border-black px-1 py-0.5">{Number(employee.base_salary).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</td>
          </tr>
        </tbody>
      </table>

      {/* DADOS DO TRABALHADOR - LINHA 2 (Verde Ciano) */}
      <table className="w-full border-collapse border border-black mb-4">
        <tbody>
          <tr className="bg-[#00FFFF] text-center font-semibold">
            <td className="border border-black px-1 py-0.5 w-[10%]">Loc.Tra</td>
            <td className="border border-black px-1 py-0.5 w-[45%] text-left">Conta de Integração</td>
            <td className="border border-black px-1 py-0.5 w-[45%] text-left">Cat.Profissional</td>
          </tr>
          <tr className="text-center">
            <td className="border border-black px-1 py-0.5">01</td>
            <td className="border border-black px-1 py-0.5 text-left">01-Integração Sede</td>
            <td className="border border-black px-1 py-0.5 text-left">{employee.professional_category || employee.role}</td>
          </tr>
        </tbody>
      </table>

      {/* TABELA DE RUBRICAS (CORPO DO RECIBO) */}
      <div className="flex-1 min-h-[300px] border border-black border-b-0 border-t-0">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-[#00FFFF] border-y border-black font-semibold text-center">
              <th className="px-1 py-0.5 text-left border-r border-black w-[10%]">CODIGO</th>
              <th className="px-1 py-0.5 text-left border-r border-black w-[35%]">DESCRIÇÃO</th>
              <th className="px-1 py-0.5 border-r border-black">QTD</th>
              <th className="px-1 py-0.5 border-r border-black">PREÇO</th>
              <th className="px-1 py-0.5 border-r border-black">ABONO/DESC</th>
              <th className="px-1 py-0.5 border-r border-black">IRPS</th>
              <th className="px-1 py-0.5 border-r border-black">SS</th>
              <th className="px-1 py-0.5">SIND</th>
            </tr>
          </thead>
          <tbody>
            {slip.lines && slip.lines.map((line, i) => (
              <tr key={i} className="text-right">
                <td className="px-1 py-0.5 text-left">{line.code}</td>
                <td className="px-1 py-0.5 text-left">{line.description}</td>
                <td className="px-1 py-0.5">{Number(line.quantity).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td className="px-1 py-0.5">{Number(line.unit_price) > 0 ? Number(line.unit_price).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2}) : ""}</td>
                <td className="px-1 py-0.5">{Number(line.amount).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</td>
                <td className="px-1 py-0.5">{line.irps_tax_percentage ? `${Number(line.irps_tax_percentage)}%` : "N"}</td>
                <td className="px-1 py-0.5">{line.is_taxable_inss ? "S" : "N"}</td>
                <td className="px-1 py-0.5">{line.is_taxable_syndicate ? "S" : "N"}</td>
              </tr>
            ))}
            <tr>
              <td colSpan={8} className="px-1 py-2 text-left">
                Observ.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* TABELA DE TOTAIS (RODAPÉ) */}
      <table className="w-full border-collapse border border-black mt-auto">
        <thead>
          <tr className="bg-[#00FFFF] text-center font-semibold">
            <th className="border border-black px-1 py-0.5">ILIQUIDO</th>
            <th className="border border-black px-1 py-0.5">TAXA SOCIAL</th>
            <th className="border border-black px-1 py-0.5">H.EXTRAS</th>
            <th className="border border-black px-1 py-0.5">IRPS</th>
            <th className="border border-black px-1 py-0.5">TAXA</th>
            <th className="border border-black px-1 py-0.5">SINDICATO</th>
          </tr>
        </thead>
        <tbody>
          <tr className="text-center font-mono">
            <td className="border border-black px-1 py-0.5">{Number(slip.gross_salary).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</td>
            <td className="border border-black px-1 py-0.5">{Number(slip.total_inss).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</td>
            <td className="border border-black px-1 py-0.5">0,00 MT</td>
            <td className="border border-black px-1 py-0.5">{Number(slip.total_irps).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</td>
            <td className="border border-black px-1 py-0.5">{employee.irps_tax_percentage ? `${Number(employee.irps_tax_percentage).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})}%` : ""}</td>
            <td className="border border-black px-1 py-0.5">{Number(slip.total_syndicate).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</td>
          </tr>
        </tbody>
      </table>

      {/* SUMÁRIO FINAL */}
      <div className="flex justify-between items-start mt-2">
        <div className="w-2/3 space-y-1">
          <p>Seguradora {"{Apolice Nº}"}</p>
          <p>Transferido do Banco</p>
          <p>Para Conta Bancária</p>
          <div className="flex gap-4">
            <p>Total Rendimentos</p>
            <p>0,00 MT</p>
          </div>
        </div>
        <div className="w-1/3 text-right">
          <div className="flex justify-between border-b border-white mb-1 font-semibold">
            <span>TOTAL DESCONTOS</span>
            <span>{Number(slip.total_deductions).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</span>
          </div>
          <div className="flex justify-between font-bold text-[11px] sm:text-sm">
            <span>LIQUIDO A RECEBER</span>
            <span>{Number(slip.net_salary).toLocaleString("pt-MZ", {minimumFractionDigits: 2, maximumFractionDigits: 2})} MT</span>
          </div>
          <p className="mt-8">Recibo {slip.id.substring(0,6).toUpperCase()}/{slip.period_year}</p>
        </div>
      </div>

      <div className="mt-12 w-full flex items-end">
         <div className="w-20">Assinatura</div>
         <div className="flex-1 border-b border-black ml-2"></div>
      </div>
    </div>
  );

  return (
    <div className="bg-[#e5e5e5] p-2 sm:p-8 flex items-center justify-center overflow-x-auto min-h-screen">
      <div className="w-[210mm] min-w-[800px] h-auto bg-white shadow-2xl flex flex-row">
        <PayslipHalf type="ORIGINAL" />
        <PayslipHalf type="DUPLICADO" />
      </div>
    </div>
  );
}
