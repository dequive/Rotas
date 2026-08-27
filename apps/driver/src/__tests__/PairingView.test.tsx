import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pairDevice } from "../api";
import { PairingView } from "../views/PairingView";

vi.mock("../api", () => ({ pairDevice: vi.fn() }));

describe("emparelhamento do dispositivo", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("rotas_device_id", "device-qa");
    vi.mocked(pairDevice).mockReset();
  });

  afterEach(cleanup);

  it("aceita apenas o código numérico de seis dígitos emitido pelo gestor", async () => {
    const onPaired = vi.fn();
    vi.mocked(pairDevice).mockResolvedValue({
      accessToken: "access",
      tenantId: "tenant-1",
      driverId: "driver-1",
      deviceId: "device-qa",
      driverName: "Motorista QA",
      sessionId: "session-1",
    });
    render(<PairingView onPaired={onPaired} />);

    const input = screen.getByRole("textbox", { name: "Código de emparelhamento" });
    const submit = screen.getByRole("button", { name: "Emparelhar dispositivo" });

    expect(input).toHaveProperty("inputMode", "numeric");
    fireEvent.change(input, { target: { value: "12A34-56" } });
    expect(input).toHaveProperty("value", "123456");
    expect(submit).not.toHaveProperty("disabled", true);
    fireEvent.click(submit);

    await waitFor(() => expect(pairDevice).toHaveBeenCalledWith("123456", "device-qa"));
    expect(onPaired).toHaveBeenCalledOnce();
  });

  it("não expõe códigos técnicos quando o emparelhamento falha", async () => {
    vi.mocked(pairDevice).mockRejectedValue(new Error("invalid_pairing_code"));
    render(<PairingView onPaired={vi.fn()} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Código de emparelhamento" }), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Emparelhar dispositivo" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Confirme o código ou peça um novo ao gestor",
    );
    expect(screen.queryByText("invalid_pairing_code")).toBeNull();
  });

  it("permite aplicar uma versão nova mesmo antes do emparelhamento", () => {
    const onUpdate = vi.fn();

    render(<PairingView onPaired={vi.fn()} onUpdate={onUpdate} />);
    fireEvent.click(screen.getByRole("button", { name: "Atualizar aplicação" }));

    expect(onUpdate).toHaveBeenCalledOnce();
  });
});
