import "fake-indexeddb/auto";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSyncStatus } from "../hooks/useSyncStatus";
import { publishPwaUpdate } from "../pwaUpdate";

describe("estado de sessão da sincronização", () => {
  it("remove o aviso de sessão expirada após um novo emparelhamento", () => {
    const { result, rerender } = renderHook(
      ({ sessionId }) => useSyncStatus(true, false, sessionId),
      { initialProps: { sessionId: "sessao-antiga" } },
    );

    act(() => window.dispatchEvent(new CustomEvent("session-expired")));
    expect(result.current.bannerState).toBe("session_expired");

    rerender({ sessionId: "sessao-nova" });
    expect(result.current.bannerState).toBe("idle");
  });
});

describe("atualização do WebAPK", () => {
  it("não perde um worker em espera anunciado antes de o React montar", () => {
    const waiting = { postMessage: () => undefined };
    const workbox = { waiting, addEventListener: () => undefined };

    publishPwaUpdate(workbox);
    const { result } = renderHook(() => useSyncStatus(true, false));

    expect(result.current.bannerState).toBe("update_available");
    expect(result.current.workboxInstance).toBe(workbox);
  });
});
