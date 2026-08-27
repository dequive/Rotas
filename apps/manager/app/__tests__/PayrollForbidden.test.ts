import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { HttpContractError } from "@rotas/http-contract";

const apiFetch = vi.fn();
vi.mock("../lib/api", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args) }));

const { loadPayrollSlips } = await import("../lib/hr-api");

describe("loadPayrollSlips", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("não converte uma recusa de permissão numa lista vazia", async () => {
    // Um 403 devolvido como [] faria a página dizer que não há processamento
    // salarial no mês, quando o que há é processamento que o utilizador não
    // pode ver. É a diferença entre 'não existe' e 'não é para si'.
    apiFetch.mockRejectedValueOnce(
      new HttpContractError("Insufficient permissions", 403, "forbidden"),
    );

    const result = await loadPayrollSlips(1, 2026);

    expect(result.status).toBe("forbidden");
    expect(result).not.toHaveProperty("slips");
  });

  it("distingue erro técnico de recusa de permissão", async () => {
    apiFetch.mockRejectedValueOnce(new HttpContractError("Boom", 500, "internal_error"));

    const result = await loadPayrollSlips(1, 2026);

    expect(result.status).toBe("error");
  });

  it("devolve os recibos quando o acesso é permitido", async () => {
    apiFetch.mockResolvedValueOnce([{ id: "slip-1", net_salary: "42000.00" }]);

    const result = await loadPayrollSlips(1, 2026);

    expect(result.status).toBe("ok");
    if (result.status === "ok") {
      expect(result.slips).toHaveLength(1);
    }
  });

  it("uma lista vazia continua a ser uma lista vazia, não um erro", async () => {
    apiFetch.mockResolvedValueOnce([]);

    const result = await loadPayrollSlips(1, 2026);

    expect(result.status).toBe("ok");
    if (result.status === "ok") {
      expect(result.slips).toEqual([]);
    }
  });
});
