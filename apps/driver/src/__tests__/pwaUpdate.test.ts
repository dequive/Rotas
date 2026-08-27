import { describe, expect, it, vi } from "vitest";
import {
  startPwaUpdateLifecycle,
  type PwaUpdateRuntime,
} from "../pwaUpdate";

function runtime(hasController = true): PwaUpdateRuntime & {
  listeners: Record<string, () => void>;
} {
  const listeners: Record<string, () => void> = {};
  return {
    listeners,
    reload: vi.fn(),
    hasController: () => hasController,
    isOnline: () => true,
    isVisible: () => true,
    subscribe: (event, listener) => {
      listeners[event] = listener;
      return () => delete listeners[event];
    },
  };
}

describe("lifecycle de atualização da PWA", () => {
  it("ativa uma versão em espera antes de montar a aplicação", async () => {
    let controlling: (() => void) | undefined;
    const postMessage = vi.fn();
    const update = vi.fn().mockResolvedValue(undefined);
    const workbox = {
      waiting: { postMessage },
      register: vi.fn().mockResolvedValue({ waiting: {}, update }),
      addEventListener: vi.fn((event: string, listener: () => void) => {
        if (event === "controlling") controlling = listener;
      }),
    };
    const environment = runtime();

    const lifecycle = await startPwaUpdateLifecycle(workbox, environment);

    expect(update).toHaveBeenCalledOnce();
    expect(postMessage).toHaveBeenCalledWith({ type: "SKIP_WAITING" });
    expect(lifecycle.shouldRender).toBe(false);
    expect(environment.reload).not.toHaveBeenCalled();

    controlling?.();
    expect(environment.reload).toHaveBeenCalledOnce();
  });

  it("verifica novamente quando a aplicação regressa ao primeiro plano", async () => {
    const update = vi.fn().mockResolvedValue(undefined);
    const workbox = {
      waiting: null,
      register: vi.fn().mockResolvedValue({ waiting: null, update }),
      addEventListener: vi.fn(),
    };
    const environment = runtime();

    const lifecycle = await startPwaUpdateLifecycle(workbox, environment);
    expect(lifecycle.shouldRender).toBe(true);
    expect(update).toHaveBeenCalledOnce();

    environment.listeners.visibilitychange();
    await vi.waitFor(() => expect(update).toHaveBeenCalledTimes(2));
  });

  it("não bloqueia nem recarrega a primeira instalação sem controlador", async () => {
    const postMessage = vi.fn();
    const update = vi.fn().mockResolvedValue(undefined);
    const workbox = {
      waiting: { postMessage },
      register: vi.fn().mockResolvedValue({ waiting: {}, update }),
      addEventListener: vi.fn(),
    };
    const environment = runtime(false);

    const lifecycle = await startPwaUpdateLifecycle(workbox, environment);

    expect(lifecycle.shouldRender).toBe(true);
    expect(update).not.toHaveBeenCalled();
    expect(postMessage).not.toHaveBeenCalled();
    expect(environment.reload).not.toHaveBeenCalled();
  });

  it("liberta o primeiro render sem esperar a instalação do worker", async () => {
    const register = vi.fn(
      () => new Promise<never>(() => undefined),
    );
    const workbox = {
      waiting: null,
      register,
      addEventListener: vi.fn(),
    };
    let settled = false;

    void startPwaUpdateLifecycle(workbox, runtime(false)).then(() => {
      settled = true;
    });
    await Promise.resolve();

    expect(register).toHaveBeenCalledOnce();
    expect(settled).toBe(true);
  });
});
