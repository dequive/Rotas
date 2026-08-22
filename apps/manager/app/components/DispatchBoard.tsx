"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Truck, Users, Check, AlertCircle, ArrowRight } from "lucide-react";
import {
  assignTripOrder,
  confirmTripOrder,
} from "../lib/trip-orders-client";
import type { TripOrder } from "../lib/trip-orders-api";
import type { Vehicle } from "../lib/vehicles-api";
import type { Driver } from "../lib/drivers-api";
import { Button } from "./ui/Button";
import { ModalDialog } from "./ui/ModalDialog";
import { StatusBadge } from "./ui/StatusBadge";

interface DispatchBoardProps {
  pendingOrders: TripOrder[];
  vehicles: Vehicle[];
  drivers: Driver[];
}

export function DispatchBoard({ pendingOrders, vehicles, drivers }: DispatchBoardProps) {
  const router = useRouter();
  const [selectedOrder, setSelectedOrder] = useState<TripOrder | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("");
  const [selectedDriverId, setSelectedDriverId] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmingOrderId, setConfirmingOrderId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const availableVehicles = vehicles.filter(v => v.status === "active");
  const availableDrivers = drivers.filter(d => d.status === "active");

  const handleAssign = async () => {
    if (!selectedOrder || !selectedVehicleId || !selectedDriverId) return;

    setIsSubmitting(true);
    setActionError(null);
    try {
      await assignTripOrder(selectedOrder.id, selectedVehicleId, selectedDriverId);
      setSelectedOrder(null);
      setSelectedVehicleId("");
      setSelectedDriverId("");
      router.refresh();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Não foi possível atribuir os recursos à ordem.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirm = async (order: TripOrder) => {
    setConfirmingOrderId(order.id);
    setActionError(null);
    try {
      await confirmTripOrder(order.id, {
        reason: "Confirmada no quadro de despacho",
      });
      router.refresh();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Não foi possível confirmar a ordem.",
      );
    } finally {
      setConfirmingOrderId(null);
    }
  };

  if (pendingOrders.length === 0) {
    return (
      <div className="mb-6 mt-4 flex flex-col items-center justify-center rounded-xl border border-border bg-surface p-8 text-center shadow-design-sm">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-success-bg text-success">
          <Check size={24} />
        </div>
        <h3 className="font-semibold text-ink">Sem ordens abertas</h3>
        <p className="mt-1 max-w-sm text-sm text-muted">Crie uma ordem de transporte para iniciar o fluxo de despacho.</p>
      </div>
    );
  }

  return (
    <div className="mb-6 mt-4 overflow-hidden rounded-xl border border-border bg-surface shadow-design-sm">
      <div className="flex items-center justify-between border-b border-border bg-surface-2 p-4">
        <h2 className="flex items-center gap-2 font-semibold text-ink">
          <ArrowRight size={18} className="text-accent-action-600" />
          Quadro de Despacho Operacional
        </h2>
        <span className="rounded-md border border-border bg-surface px-2 py-1 text-xs font-semibold text-muted">
          {pendingOrders.length} ordens abertas
        </span>
      </div>

      {actionError && (
        <p role="alert" className="m-4 rounded-md border border-error-border bg-error-bg px-3 py-2 text-sm text-error">
          <AlertCircle size={14} className="mr-1 inline" /> {actionError}
        </p>
      )}

      <div className="divide-y divide-border">
        {pendingOrders.map((order) => (
          <div key={order.id} className="flex flex-col gap-4 p-4 transition-colors hover:bg-surface-2 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="rounded bg-surface-2 px-2 py-0.5 text-xs font-bold text-muted">
                  {order.customer_reference || order.id.slice(0,8).toUpperCase()}
                </span>
                <span className="font-semibold text-ink">
                  {order.client_id ? "Cliente associado" : "Cliente Interno"}
                </span>
                <StatusBadge status={order.status} />
              </div>
              <p className="text-sm text-muted">
                <span className="font-medium text-ink">{order.origin}</span> → <span className="font-medium text-ink">{order.destination}</span>
              </p>
              <p className="mt-1 text-xs text-muted">
                Carga: {order.cargo_type || "Geral"} • Peso: {order.estimated_weight || 0} kg
              </p>
            </div>

            {order.status === "draft" ? (
              <Button
                size="sm"
                loading={confirmingOrderId === order.id}
                onClick={() => handleConfirm(order)}
              >
                Confirmar ordem
              </Button>
            ) : (
              <Button size="sm" onClick={() => setSelectedOrder(order)}>
                Atribuir motorista
              </Button>
            )}
          </div>
        ))}
      </div>

      <ModalDialog
        open={selectedOrder !== null}
        onClose={() => setSelectedOrder(null)}
        title="Despachar viagem"
      >
        {selectedOrder && (
          <>
            <p className="border-b border-border bg-surface-2 px-6 py-3 text-xs text-muted">{selectedOrder.origin} → {selectedOrder.destination}</p>
            <div className="p-6 flex flex-col gap-5">
              <div>
                <label htmlFor="dispatch-vehicle" className="mb-1 flex items-center gap-2 text-sm font-medium text-ink">
                  <Truck size={14} className="text-muted" /> Selecionar viatura
                </label>
                <select
                  id="dispatch-vehicle"
                  className="w-full rounded-lg border border-border-strong bg-surface p-2.5 text-sm text-ink outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft"
                  value={selectedVehicleId}
                  onChange={(e) => setSelectedVehicleId(e.target.value)}
                >
                  <option value="">-- Escolha uma viatura livre --</option>
                  {availableVehicles.map(v => (
                    <option key={v.id} value={v.id}>{v.plate} ({v.brand} {v.model})</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="dispatch-driver" className="mb-1 flex items-center gap-2 text-sm font-medium text-ink">
                  <Users size={14} className="text-muted" /> Selecionar motorista
                </label>
                <select
                  id="dispatch-driver"
                  className="w-full rounded-lg border border-border-strong bg-surface p-2.5 text-sm text-ink outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft"
                  value={selectedDriverId}
                  onChange={(e) => setSelectedDriverId(e.target.value)}
                >
                  <option value="">-- Escolha um motorista livre --</option>
                  {availableDrivers.map(d => (
                    <option key={d.id} value={d.id}>{d.full_name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-border bg-surface-2 p-4">
              <Button
                variant="secondary"
                onClick={() => setSelectedOrder(null)}
                disabled={isSubmitting}
              >
                Cancelar
              </Button>
              <Button
                onClick={handleAssign}
                disabled={!selectedVehicleId || !selectedDriverId || isSubmitting}
                loading={isSubmitting}
              >
                Confirmar despacho
              </Button>
            </div>
          </>
        )}
      </ModalDialog>
    </div>
  );
}
