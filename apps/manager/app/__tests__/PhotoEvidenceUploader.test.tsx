import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { PhotoEvidenceUploader } from "../oficina/components/PhotoEvidenceUploader";

describe("PhotoEvidenceUploader", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders label and handles successful file upload returning server sha256_hash", async () => {
    const handleUpload = vi.fn();
    const mockResponse = {
      id: "img-001",
      url: "/uploads/img-001.jpg",
      sha256_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      created_at: "2026-07-22T14:30:00Z",
    };

    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(
      <PhotoEvidenceUploader
        label="Evidência Fotográfica de Check-in"
        onUpload={handleUpload}
      />
    );

    expect(screen.getByText("Evidência Fotográfica de Check-in")).toBeInTheDocument();

    const file = new File(["dummy content"], "evidence.jpg", { type: "image/jpeg" });
    const input = screen.getByLabelText("Evidência Fotográfica de Check-in");

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/files/upload",
        expect.objectContaining({
          method: "POST",
        })
      );
      expect(handleUpload).toHaveBeenCalledWith(mockResponse);
    });
  });

  it("blocks non-image files and displays validation error", async () => {
    render(
      <PhotoEvidenceUploader
        label="Evidência Fotográfica"
      />
    );

    const pdfFile = new File(["dummy content"], "document.pdf", { type: "application/pdf" });
    const input = screen.getByLabelText("Evidência Fotográfica");

    fireEvent.change(input, { target: { files: [pdfFile] } });

    await waitFor(() => {
      expect(screen.getByText("Apenas ficheiros de imagem são permitidos.")).toBeInTheDocument();
    });
  });
});
