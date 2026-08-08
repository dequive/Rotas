"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { SidebarLayout } from "../../../components/SidebarLayout";
import VehicleHistoryPanel from "../../components/VehicleHistoryPanel";
import { bffRequest } from "@/app/lib/bff";

interface ReceptionDetail {
  id: string;
  reception_number: string;
  vehicle_id: string;
  received_at: string;
  odometer_at_reception: number;
  reported_issues: string | null;
  visual_condition: string | null;
  fuel_level: string;
  delivered_by_name: string | null;
  delivered_by_phone: string | null;
  pickup_authorized_by_name: string | null;
  pickup_authorized_by_phone: string | null;
  status: string;
  photos: Array<{ id: string; file_id: string; caption: string | null }>;
}

export default function ReceptionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const receptionId = (params?.id as string) || "REC-2026-0005";

  const [detail, setDetail] = useState<ReceptionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchDetail() {
      try {
        const res = await bffRequest(`/api/v1/workshop/receptions/${receptionId}`);
        if (res.ok) {
          const data = await res.json();
          setDetail(data);
        } else {
          // Demo fallback detail
          setDetail({
            id: receptionId,
            reception_number: receptionId.startsWith("REC-") ? receptionId : "REC-2026-0005",
            vehicle_id: "veh-demo-01",
            received_at: new Date().toISOString(),
            odometer_at_reception: 48500,
            reported_issues: "Mudança de óleo sintético 5W30 e calibração de discos de travão",
            visual_condition: "Sem mossas visíveis. Pequeno arranhão na porta traseira esquerda.",
            fuel_level: "half",
            delivered_by_name: "João Muchanga",
            delivered_by_phone: "+258 84 123 4567",
            pickup_authorized_by_name: "João Muchanga",
            pickup_authorized_by_phone: "+258 84 123 4567",
            status: "received",
            photos: [],
          });
        }
      } catch (err) {
        setDetail({
          id: receptionId,
          reception_number: "REC-2026-0005",
          vehicle_id: "veh-demo-01",
          received_at: new Date().toISOString(),
          odometer_at_reception: 48500,
          reported_issues: "Mudança de óleo sintético 5W30",
          visual_condition: "Bom estado geral",
          fuel_level: "half",
          delivered_by_name: "João Muchanga",
          delivered_by_phone: "+258 84 123 4567",
          pickup_authorized_by_name: "João Muchanga",
          pickup_authorized_by_phone: "+258 84 123 4567",
          status: "received",
          photos: [],
        });
      } finally {
        setIsLoading(false);
      }
    }
    fetchDetail();
  }, [receptionId]);

  if (isLoading) {
    return (
      <SidebarLayout active="recepcao">
        <div className="max-w-5xl mx-auto p-6 text-center text-slate-500 text-xs animate-pulse">
          A carregar registo de recepção {receptionId}...
        </div>
      </SidebarLayout>
    );
  }

  return (
    <SidebarLayout active="recepcao">
      <div className="max-w-6xl mx-auto space-y-6 pb-12">
        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-200 pb-4 gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2.5 py-0.5 text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded">
                {detail?.reception_number}
              </span>
              <span className="px-2 py-0.5 text-[11px] font-semibold text-emerald-800 bg-emerald-100 rounded-full">
                {detail?.status.toUpperCase()}
              </span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 mt-1">Check-in de Viatura Confirmado</h1>
          </div>

          {/* Action CTAs */}
          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => router.push(`/oficina/orcamentos/novo?reception_id=${detail?.id}`)}
              className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm"
            >
              🟣 Criar Orçamento Comercial (ORC-2026-XXXX)
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Reception Information */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white p-5 border border-slate-200 rounded-xl shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-2">
                Resumo da Ficha de Entrada
              </h2>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-slate-500 block">Data/Hora da Entrada</span>
                  <span className="font-semibold text-slate-800">
                    {detail?.received_at ? new Date(detail.received_at).toLocaleString("pt-MZ") : "N/D"}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500 block">Odómetro Registado</span>
                  <span className="font-semibold text-slate-800">{detail?.odometer_at_reception} km</span>
                </div>

                <div>
                  <span className="text-slate-500 block">Nível de Combustível</span>
                  <span className="font-semibold text-slate-800 uppercase">{detail?.fuel_level}</span>
                </div>

                <div>
                  <span className="text-slate-500 block">Entregue Por</span>
                  <span className="font-semibold text-slate-800">{detail?.delivered_by_name || "N/D"}</span>
                  <span className="text-[10px] text-slate-500 block">{detail?.delivered_by_phone}</span>
                </div>

                <div>
                  <span className="text-slate-500 block">Autorizado no Levantamento</span>
                  <span className="font-semibold text-slate-800">{detail?.pickup_authorized_by_name || "N/D"}</span>
                  <span className="text-[10px] text-slate-500 block">{detail?.pickup_authorized_by_phone}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 space-y-2 text-xs">
                <div>
                  <span className="font-semibold text-slate-700 block">Avarias & Sintomas Reportados:</span>
                  <p className="text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 mt-1">
                    {detail?.reported_issues || "Nenhum sintoma específico registado."}
                  </p>
                </div>

                <div>
                  <span className="font-semibold text-slate-700 block">Condição Visual de Entrada:</span>
                  <p className="text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 mt-1">
                    {detail?.visual_condition || "Viatura sem danos visíveis reportados."}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Vehicle Intervention History Panel */}
          <div className="lg:col-span-1">
            <VehicleHistoryPanel vehicleId={detail?.vehicle_id || null} />
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
