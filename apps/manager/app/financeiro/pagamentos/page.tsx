import { requireSession } from "../../../lib/auth";
import { SidebarLayout } from "../../../components/SidebarLayout";
import { PageHeader } from "../../../components/ui/PageHeader";
import { loadSupplierInvoices } from "../../../lib/payables-api";
import { loadThirdParties } from "../../../lib/third-party-api";
import { PayablesTableClient, InvoiceWithSupplier } from "./PayablesTableClient";

export default async function PagamentosPage() {
  await requireSession();
  
  // Fazemos os dois pedidos em paralelo para ser super rápido
  const [invoices, thirdParties] = await Promise.all([
    loadSupplierInvoices(),
    loadThirdParties()
  ]);

  // Mapa rápido de ID -> Nome para não fazermos loops gigantes
  const tpMap = new Map(thirdParties.map(tp => [tp.id, tp.name]));

  // Cruzamos a Fatura com o Nome do Fornecedor correspondente
  const mappedInvoices: InvoiceWithSupplier[] = invoices.map(inv => ({
    ...inv,
    supplierName: tpMap.get(inv.third_party_id) || "Fornecedor Desconhecido"
  }));

  const pendingCount = mappedInvoices.filter(i => i.status !== "paid").length;

  return (
    <SidebarLayout active="financeiro">
      <div className="w-full space-y-6">
        <PageHeader
          eyebrow="Tesouraria"
          title="Contas a Pagar (P2P)"
          description={`${pendingCount} faturas aguardam liquidação`}
        />
        
        <PayablesTableClient initialInvoices={mappedInvoices} />
      </div>
    </SidebarLayout>
  );
}
