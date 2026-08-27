import { notFound } from "next/navigation";

import { SidebarLayout } from "../../../components/SidebarLayout";
import { WorkOrderDetailClient } from "../../components/WorkOrderDetailClient";
import { requireSession } from "../../../lib/auth";
import { loadWorkOrderDetail, loadWorkOrderProfitability } from "../../../lib/workshop-api";

export default async function WorkOrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await requireSession();
  const { id } = await params;
  let detail;
  try {
    detail = await loadWorkOrderDetail(id);
  } catch (error) {
    if (error instanceof Error && error.message.toLowerCase().includes("not found")) notFound();
    throw error;
  }
  const profitability = await loadWorkOrderProfitability(id).catch(() => null);

  return (
    <SidebarLayout active="os-oficina">
      <div className="mx-auto max-w-7xl p-6">
        <WorkOrderDetailClient detail={detail} profitability={profitability} role={session.role} userId={session.userId} />
      </div>
    </SidebarLayout>
  );
}
