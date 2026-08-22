import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TripFormModal } from "../components/TripFormModal";
import type { KnownRoute } from "../lib/known-routes-api";
import type { Vehicle } from "../lib/vehicles-api";
import type { Driver } from "../lib/drivers-api";
import type { Contract } from "../lib/contracts-api";
import type { DriverDespachoTier } from "../lib/operations-admin-api";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: vi.fn(),
  }),
}));

const mockVehicles: Vehicle[] = [
  {
    id: "veh-1",
    plate: "ABC-123-MC",
    brand: "Volvo",
    model: "FH460",
    year: 2021,
    category: "pesado",
    status: "active",
    current_km: 120000,
    fuel_type: "diesel",
    color: "Branco",
    avg_consumption_target: 32.5,
    fuel_limit_daily: 200,
    documents: null,
  },
];

const mockDrivers: Driver[] = [
  {
    id: "drv-1",
    full_name: "Mateus Cossa",
    phone: "258840000001",
    email: "mateus.cossa@rotas.local",
    license_number: "C-100234",
    license_category: "C",
    license_valid_until: "2027-12-31",
    passport_number: null,
    passport_valid_until: null,
    bi_number: null,
    bi_valid_until: null,
    employment_type: "efectivo",
    status: "active",
    score: 100,
  },
];

const mockContracts: Contract[] = [
  {
    id: "ctr-1",
    client_id: "cli-1",
    client_name: "Cimentos de Moçambique",
    contract_reference: "CTR-2026-001",
    title: "Contrato Transporte Cimento",
    status: "active",
    service_type: "freight",
    billing_cycle: "monthly",
    billing_basis: "delivery_proof",
    currency: "MZN",
    default_unit_price: 18000,
    requires_load_permit: true,
    requires_delivery_proof: true,
    starts_at: "2026-01-01",
    ends_at: "2026-12-31",
  },
];

const mockKnownRoutes: KnownRoute[] = [
  {
    id: "route-1",
    origin: "Maputo",
    destination: "Beira",
    distance_km: 530,
    avg_fuel_liters: 172,
    despacho_vazio: 2500,
    despacho_carregado: 4500,
    notes: "Rota principal",
    is_active: true,
  },
];

const mockTiers: DriverDespachoTier[] = [
  { min_km: 100, max_km: 1000, amount: 2500, label: "Longa Curso", code: "LC-1" },
];

describe("TripFormModal — High Volume Trip Scheduling & Load Permit Verification", () => {
  it("renders modal trigger and opens with full business fields including Load Permit", async () => {
    render(
      <TripFormModal
        vehicles={mockVehicles}
        drivers={mockDrivers}
        contracts={mockContracts}
        knownRoutes={mockKnownRoutes}
        despacheTiers={mockTiers}
      />
    );

    // Trigger modal open
    const openBtn = screen.getByRole("button", { name: /nova viagem/i });
    fireEvent.click(openBtn);

    expect(screen.getByText("Nova Viagem de Transporte")).toBeInTheDocument();
    expect(screen.getByText(/Número do Load Permit/i)).toBeInTheDocument();
    expect(screen.getByText(/Guia de Transporte Fiscal \(Gerada Automaticamente\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Estado da Carga/i)).toBeInTheDocument();
  });

  it("calculates proportional fuel & despacho when switching between loaded_empty and loaded_loaded", async () => {
    render(
      <TripFormModal
        vehicles={mockVehicles}
        drivers={mockDrivers}
        contracts={mockContracts}
        knownRoutes={mockKnownRoutes}
        despacheTiers={mockTiers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /nova viagem/i }));

    // Select Catalog Route (Maputo -> Beira 530km)
    const routeSelect = screen.getByLabelText(/Destino do Catálogo/i);
    fireEvent.change(routeSelect, { target: { value: "route-1" } });

    // Select Vehicle
    const vehicleSelect = screen.getByLabelText(/Viatura/i);
    fireEvent.change(vehicleSelect, { target: { value: "veh-1" } });

    // Initial state: loaded_empty (multiplier 1.0x -> Fuel 172L)
    await waitFor(() => {
      expect(screen.getByText(/Combustível Estimado/i)).toBeInTheDocument();
      expect(screen.getByText(/172/)).toBeInTheDocument();
    });

    // Switch state to loaded_loaded (multiplier 1.8x -> Fuel 310L)
    const loadStateSelect = screen.getByLabelText(/Estado da Carga/i);
    fireEvent.change(loadStateSelect, { target: { value: "loaded_loaded" } });

    await waitFor(() => {
      expect(screen.getByText(/310/)).toBeInTheDocument();
    });
  });

  it("submits full payload including Load Permit and waybill to /api/trips", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ id: "trip-new-1" }),
    } as Response);

    render(
      <TripFormModal
        vehicles={mockVehicles}
        drivers={mockDrivers}
        contracts={mockContracts}
        knownRoutes={mockKnownRoutes}
        despacheTiers={mockTiers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /nova viagem/i }));

    // Fill form
    fireEvent.change(screen.getByLabelText(/Viatura/i), { target: { value: "veh-1" } });
    fireEvent.change(screen.getByLabelText(/Motorista/i), { target: { value: "drv-1" } });
    fireEvent.change(screen.getByLabelText(/Origem/i), { target: { value: "Maputo" } });
    fireEvent.change(screen.getByLabelText(/Destino \(Preenchido/i), { target: { value: "Beira" } });
    fireEvent.change(screen.getByPlaceholderText(/Ex: LP-2026-9874/i), {
      target: { value: "LP-2026-9874" },
    });

    // Submit
    const submitBtn = screen.getByRole("button", { name: /Criar e Fechar/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/trips",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("LP-2026-9874"),
        })
      );
    });

    fetchSpy.mockRestore();
  });
});
