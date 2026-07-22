import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SignatureCanvas from "../oficina/components/SignatureCanvas";
import VehicleHistoryPanel from "../oficina/components/VehicleHistoryPanel";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
  }),
  useParams: () => ({ id: "REC-2026-0005" }),
}));

describe("Recepção de Viaturas & Componentes de Check-in", () => {
  it(" SignatureCanvas permite alternar entre Assinatura Ecrã e Foto Papel", () => {
    const onCaptured = vi.fn();
    render(<SignatureCanvas onSignatureCaptured={onCaptured} />);

    expect(screen.getByText(/Assinatura Ecrã/i)).toBeDefined();
    expect(screen.getByText(/Foto Papel Assinado/i)).toBeDefined();

    // Alternar para foto papel
    fireEvent.click(screen.getByText(/Foto Papel Assinado/i));
    expect(screen.getByText(/Tire uma foto ou carregue a imagem/i)).toBeDefined();
  });

  it(" VehicleHistoryPanel lida com viatura sem histórico anterior (Empty State)", async () => {
    render(<VehicleHistoryPanel vehicleId="veh-new-99" />);

    expect(screen.getByText(/Histórico de Intervenções/i)).toBeDefined();
  });
});
