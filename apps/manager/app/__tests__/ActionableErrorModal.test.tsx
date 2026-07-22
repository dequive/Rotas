import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeAll } from "vitest";
import { ActionableErrorModal } from "../oficina/components/ActionableErrorModal";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
  };
});

describe("ActionableErrorModal", () => {
  it("renders specific CTA for quantity_exceeds_approved_reservation 409 error", () => {
    const handleAction = vi.fn();
    render(
      <ActionableErrorModal
        open={true}
        onClose={() => {}}
        errorCode="quantity_exceeds_approved_reservation"
        errorMessage="Quantidade solicitada excede o tecto aprovado"
        onAction={handleAction}
      />
    );

    expect(screen.getByText("Quantidade Excede Reserva Aprovada")).toBeInTheDocument();
    const actionBtn = screen.getByRole("button", { name: /Criar Orçamento Suplementar/i });
    expect(actionBtn).toBeInTheDocument();

    fireEvent.click(actionBtn);
    expect(handleAction).toHaveBeenCalledWith("create_supplemental_quote");
  });

  it("renders specific CTA for work_order_already_billed 409 error", () => {
    const handleAction = vi.fn();
    render(
      <ActionableErrorModal
        open={true}
        onClose={() => {}}
        errorCode="work_order_already_billed"
        errorMessage="Ordem de serviço já faturada"
        onAction={handleAction}
      />
    );

    expect(screen.getByText("Ordem de Serviço Já Faturada")).toBeInTheDocument();
    const actionBtn = screen.getByRole("button", { name: /Ver Fatura Vinculada/i });
    expect(actionBtn).toBeInTheDocument();

    fireEvent.click(actionBtn);
    expect(handleAction).toHaveBeenCalledWith("view_linked_invoice");
  });

  it("renders default fallback CTA when error code is generic or unknown", () => {
    const handleClose = vi.fn();
    render(
      <ActionableErrorModal
        open={true}
        onClose={handleClose}
        errorCode="unknown_server_error"
        errorMessage="Erro inesperado"
      />
    );

    expect(screen.getByText("Erro Inesperado")).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: /Tentar Novamente/i });
    expect(retryBtn).toBeInTheDocument();
  });
});
