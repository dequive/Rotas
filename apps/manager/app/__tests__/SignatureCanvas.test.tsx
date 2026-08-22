import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignatureCanvas from "../oficina/components/SignatureCanvas";

describe("SignatureCanvas Component", () => {
  it("renders digital canvas tab by default and allows clearing canvas", () => {
    const onCaptured = vi.fn();
    render(<SignatureCanvas onSignatureCaptured={onCaptured} />);

    expect(screen.getByText(/Assinatura do Cliente/i)).toBeDefined();
    expect(screen.getByText(/Assine com dedo, caneta ou rato acima/i)).toBeDefined();

    const clearBtn = screen.getByText(/Limpar Ecrã/i);
    expect(clearBtn).toBeDefined();
    fireEvent.click(clearBtn);
  });

  it("switches to paper signature tab and displays file uploader instructions", () => {
    const onCaptured = vi.fn();
    render(<SignatureCanvas onSignatureCaptured={onCaptured} />);

    const paperTabBtn = screen.getByText(/Foto Papel Assinado/i);
    fireEvent.click(paperTabBtn);

    expect(screen.getByText(/Tire uma foto ou carregue a imagem da folha de check-in física/i)).toBeDefined();
  });

  it("triggers onSignatureCaptured callback when digital signature is confirmed", async () => {
    const onCaptured = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "signature-file-1",
            sha256_hash: "a8f9c0e123456789abcdef0123456789abcdef0123456789abcdef0123456789",
          }),
          {
            status: 201,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );
    render(<SignatureCanvas onSignatureCaptured={onCaptured} />);

    // Mock HTMLCanvasElement.toBlob
    const canvas = document.querySelector("canvas");
    if (canvas) {
      canvas.toBlob = (callback: BlobCallback) => {
        const blob = new Blob(["fake-image-bytes"], { type: "image/png" });
        callback(blob);
      };
    }

    const confirmBtn = screen.getByText(/Confirmar Assinatura Digital/i);
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onCaptured).toHaveBeenCalledWith(
        "signature-file-1",
        "a8f9c0e123456789abcdef0123456789abcdef0123456789abcdef0123456789",
      );
    });
    vi.unstubAllGlobals();
  });
});
