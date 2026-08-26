import { createElement } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  activateWaitingServiceWorker,
  SyncStatusBanner,
} from "../components/SyncStatusBanner";

afterEach(cleanup);

describe("atualização segura do PWA", () => {
  it("só recarrega depois de o novo service worker controlar a página", () => {
    let onControlling: (() => void) | undefined;
    const postMessage = vi.fn();
    const reload = vi.fn();
    const workbox = {
      waiting: { postMessage },
      addEventListener: vi.fn((event: string, handler: () => void) => {
        if (event === "controlling") onControlling = handler;
      }),
    };

    activateWaitingServiceWorker(workbox, reload);

    expect(postMessage).toHaveBeenCalledWith({ type: "SKIP_WAITING" });
    expect(reload).not.toHaveBeenCalled();

    onControlling?.();
    expect(reload).toHaveBeenCalledOnce();
  });
});

describe("recuperação de sessão expirada", () => {
  it("confirma a remoção dos dados locais antes do novo emparelhamento", () => {
    const onRePair = vi.fn();

    render(createElement(SyncStatusBanner, {
      status: {
        bannerState: "session_expired",
        pendingCount: 0,
        errorCount: 0,
        workboxInstance: null,
      },
      onRePair,
    }));

    fireEvent.click(screen.getByRole("button", { name: "Voltar a emparelhar" }));

    expect(onRePair).not.toHaveBeenCalled();
    expect(screen.getByText(/os dados locais desta sessão serão removidos/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Limpar e emparelhar" }));

    expect(onRePair).toHaveBeenCalledOnce();
  });
});
