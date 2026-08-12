import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({ apiFetch: vi.fn() }));

import { apiFetch } from "../lib/api";
import { loadFleetHistories } from "../lib/fleet-history-api";
import { loadDriverDespachoTable } from "../lib/operations-admin-api";

const request = vi.mocked(apiFetch);

describe("operational loaders without demo fallback", () => {
  beforeEach(() => request.mockReset());

  it("uses an empty disabled dispatch table when the API says it is unconfigured", async () => {
    request.mockResolvedValue({ configured: false, table: null });
    await expect(loadDriverDespachoTable()).resolves.toEqual({
      configured: false,
      table: {
        enabled: false,
        table_name: "",
        table_reference: null,
        currency: "MZN",
        effective_from: null,
        min_long_course_km: 0,
        entry_mode: "manual",
        tiers: [],
      },
      source: "api",
      message: null,
    });
  });

  it("returns a real empty fleet-history state when no entities exist", async () => {
    request.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    await expect(loadFleetHistories()).resolves.toEqual({
      vehicleHistory: null,
      driverHistory: null,
      source: "api",
      message: "Registe ao menos uma viatura e um motorista para ver históricos.",
    });
  });
});
