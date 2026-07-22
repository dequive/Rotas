import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeAll } from "vitest";
import { AcceptQuoteModal } from "../oficina/components/AcceptQuoteModal";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
  };
});

describe("AcceptQuoteModal", () => {
  it("renders quote details and enforces required fields before submission", async () => {
    const handleAccept = vi.fn().mockResolvedValue(undefined);

    render(
      <AcceptQuoteModal
        open={true}
        onClose={() => {}}
        quoteNumber="ORC-2026-0042"
        totalAmount={12500}
        onAccept={handleAccept}
      />
    );

    // Verify quote number and MT currency displayed
    expect(screen.getByText(/ORC-2026-0042/i)).toBeInTheDocument();
    expect(screen.getByText(/MT/i)).toBeInTheDocument();

    // Submit button should be disabled initially (no channel selected, name empty)
    const submitBtn = screen.getByRole("button", { name: /Aceitar e Gerar OS/i });
    expect(submitBtn).toBeDisabled();

    // Select channel "WhatsApp"
    const whatsappOption = screen.getByText("WhatsApp");
    fireEvent.click(whatsappOption);

    // Submit button still disabled (person name empty)
    expect(submitBtn).toBeDisabled();

    // Fill person name
    const input = screen.getByPlaceholderText(/ex: João Silva/i);
    fireEvent.change(input, { target: { value: "Maria Santos" } });

    // Submit button is now enabled
    expect(submitBtn).not.toBeDisabled();

    // Submit
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleAccept).toHaveBeenCalledWith({
        acceptance_channel: "whatsapp",
        accepted_by_person_name: "Maria Santos",
      });
    });
  });
});
