import { describe, expect, it } from "vitest";
import {
  documentLabel,
  humanizeCode,
  loadStateLabel,
  syncEntityLabel,
  syncStatusLabel,
  tripStatusLabel,
} from "../labels";

/**
 * Fronteira de persona: o motorista nunca pode ler um código interno do
 * backend. Estes testes fixam o vocabulário canónico e garantem que nada sai
 * em snake_case, mesmo para valores que este build não conhece.
 */

const INTERNAL_CODE = /[a-z]+_[a-z]+/;

describe("rótulos do motorista", () => {
  it("traduz todo o lifecycle da viagem", () => {
    const esperado: Record<string, string> = {
      draft: "Rascunho",
      planned: "Planeada",
      dispatch_pending: "A aguardar despacho",
      dispatched: "Despachada",
      in_progress: "Em curso",
      delayed: "Atrasada",
      incident: "Com incidente",
      arrived: "Chegada ao destino",
      delivered: "Entregue",
      closed: "Concluída",
      cancelled: "Cancelada",
    };
    for (const [codigo, rotulo] of Object.entries(esperado)) {
      expect(tripStatusLabel(codigo)).toBe(rotulo);
    }
  });

  it("traduz o padrão de carga apresentado no ecrã inicial", () => {
    expect(loadStateLabel("loaded_empty")).toBe("Ida carregada, volta vazia");
    expect(loadStateLabel("loaded_loaded")).toBe("Ida e volta carregadas");
    expect(loadStateLabel(null)).toBe("Carga por confirmar");
  });

  it("traduz documentos canónicos e requisitos com prefixo de política", () => {
    expect(documentLabel("load_permit")).toBe("Autorização de carregamento (Load Permit)");
    expect(documentLabel("cargo_manifest")).toBe("Manifesto de carga");
    expect(documentLabel("transport_guide")).toBe("Guia de transporte");
    expect(documentLabel("guia_remessa")).toBe("Guia de remessa");
    expect(documentLabel("transport_document:guia_remessa")).toBe("Guia de remessa");
    expect(documentLabel("transport_document:dav")).toBe("DAV — Declaração de Aprovação de Viagem");
  });

  it("traduz a fila offline", () => {
    expect(syncEntityLabel("fuel_log")).toBe("Abastecimento");
    expect(syncEntityLabel("trip_stop")).toBe("Paragem");
    expect(syncStatusLabel("dead_letter")).toBe("Bloqueado — precisa de revisão");
    expect(syncStatusLabel("local_only")).toBe("Guardado no telemóvel");
  });

  it("nunca devolve snake_case para valores desconhecidos", () => {
    const desconhecidos = [
      "some_new_status",
      "transport_document:documento_do_tenant",
      "weird_entity_type",
    ];
    for (const valor of desconhecidos) {
      for (const rotulo of [
        tripStatusLabel(valor),
        loadStateLabel(valor),
        documentLabel(valor),
        syncEntityLabel(valor),
        syncStatusLabel(valor),
      ]) {
        expect(rotulo).not.toMatch(INTERNAL_CODE);
        expect(rotulo).not.toContain("_");
      }
    }
  });

  it("não improvisa rótulos ingleses para códigos desconhecidos", () => {
    expect(tripStatusLabel("some_new_status")).toBe("Estado por confirmar");
    expect(loadStateLabel("some_new_pattern")).toBe("Carga por confirmar");
    expect(documentLabel("some_new_document")).toBe("Documento");
    expect(syncEntityLabel("some_new_entity")).toBe("Registo");
    expect(syncStatusLabel("some_new_sync_status")).toBe("Estado desconhecido");
  });

  it("humaniza sem devolver vazio", () => {
    expect(humanizeCode("dispatch_pending")).toBe("Dispatch pending");
    expect(humanizeCode("")).toBe("—");
    expect(humanizeCode("", "Documento")).toBe("Documento");
  });
});
