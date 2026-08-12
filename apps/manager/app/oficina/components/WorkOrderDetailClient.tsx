"use client";

import { useState } from "react";
import type { WorkOrderDetail, WorkOrderProfitability } from "../../lib/workshop-api";

export function WorkOrderDetailClient({ detail, profitability }: { detail: WorkOrderDetail; profitability: WorkOrderProfitability; role: string; userId: string }) {
  const [tab, setTab] = useState("Operação");
  return <div>
    <h1>{detail.work_order.work_order_number}</h1>
    <p>{detail.tasks[0]?.description ?? "Sem tarefas"}</p>
    <p>{detail.blockers.incomplete_tasks} tarefa(s) incompleta(s)</p>
    <nav>
      {['Operação', 'Peças', 'Rentabilidade'].map((name) => <button key={name} onClick={() => setTab(name)}>{name}</button>)}
    </nav>
    {tab === 'Peças' && <div>{detail.parts_issued.map((part) => <div key={part.inventory_id}><span>{part.sku}</span><span>{part.issued_quantity}</span><span>{part.net_quantity} {part.unit}</span></div>)}</div>}
    {tab === 'Rentabilidade' && <div><h2>Margem bruta</h2><span>{profitability.gross_profit_mzn.toLocaleString('pt-MZ', { minimumFractionDigits: 2 })} MT</span></div>}
  </div>;
}
