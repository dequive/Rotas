import { requireSession } from "@/app/lib/auth";
import { apiFetch } from "@/app/lib/api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { EmpresaFormClient } from "./EmpresaFormClient";

type DocumentProfile = {
  id: string;
  tenant_id: string;
  logo_file_id: string | null;
  legal_name: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  province: string | null;
  country: string;
  phone: string | null;
  email: string | null;
  website: string | null;
  bank_name: string | null;
  bank_account: string | null;
  bank_nib: string | null;
  invoice_prefix: string;
  invoice_seq_padding: number;
  invoice_start_seq: number;
  per_type_sequences: boolean;
  payment_conditions: string;
  invoice_footer: string | null;
  show_bank_details: boolean;
  show_logo: boolean;
  created_at: string;
  updated_at: string;
};

async function getDocumentProfile(): Promise<DocumentProfile | null> {
  try {
    return await apiFetch<DocumentProfile>("/api/v1/tenants/me/document-profile", {
      revalidate: 0,
    });
  } catch {
    return null;
  }
}

export default async function EmpresaPage() {
  await requireSession();
  const profile = await getDocumentProfile();

  return (
    <SidebarLayout active="empresa">
      <div className="w-full max-w-4xl mx-auto space-y-6">
        <div className="page-header">
          <div>
            <h1>Empresa</h1>
            <p>Perfil da empresa para documentos emitidos (faturas, recibos, guias)</p>
          </div>
        </div>
        <EmpresaFormClient initialProfile={profile} />
      </div>
    </SidebarLayout>
  );
}
