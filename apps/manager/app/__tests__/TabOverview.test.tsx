import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TabOverview from "../viaturas/[id]/TabOverview";
import { bffRequest } from "../lib/bff";

vi.mock("../lib/bff", () => ({
  bffRequest: vi.fn(),
}));

const requestMock = vi.mocked(bffRequest);

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TabOverview", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("uses the versioned checklist collection endpoint", async () => {
    requestMock
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([]));

    render(<TabOverview vehicleId="vehicle-123" />);

    await waitFor(() => expect(requestMock).toHaveBeenCalledTimes(2));
    expect(requestMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/checklists?vehicle_id=vehicle-123&limit=5",
    );
  });

  it("shows a checklist error instead of presenting a failed request as empty", async () => {
    requestMock
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ detail: "Method Not Allowed" }, 405));

    render(<TabOverview vehicleId="vehicle-123" />);

    expect(
      await screen.findByText("Não foi possível carregar as checklists."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Nenhuma checklist registada.")).not.toBeInTheDocument();
  });
});
