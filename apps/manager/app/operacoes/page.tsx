import { requireSession } from "../lib/auth";
import { SidebarLayout } from "../components/SidebarLayout";
import { PageHeader } from "../components/ui/PageHeader";
import { ControlTowerClient } from "./ControlTowerClient";

export default async function OperacoesPage() {
  await requireSession();

  return (
    <SidebarLayout active="operacoes">
      <PageHeader
        eyebrow="Logística"
        title="Torre de Controlo"
        description="Gestão de Tráfego e Movimentação de Viagens em Tempo Real"
      />
      
      <section className="pt-4">
        <ControlTowerClient />
      </section>
    </SidebarLayout>
  );
}
