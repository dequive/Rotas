export interface WaitingServiceWorkerController {
  waiting?: { postMessage: (message: { type: string }) => void } | null;
  addEventListener: (
    event: "controlling" | "waiting",
    listener: () => void,
    options?: { once?: boolean },
  ) => void;
  messageSW?: (message: { type: string }) => void;
}

interface PwaRegistration {
  waiting?: unknown | null;
  update: () => Promise<unknown>;
}

export interface DriverWorkboxController extends WaitingServiceWorkerController {
  register: () => Promise<PwaRegistration | undefined>;
}

export interface PwaUpdateRuntime {
  reload: () => void;
  hasController: () => boolean;
  isOnline: () => boolean;
  isVisible: () => boolean;
  subscribe: (
    event: "visibilitychange" | "online",
    listener: () => void,
  ) => () => void;
}

type UpdateListener = (workbox: WaitingServiceWorkerController) => void;

let pendingUpdate: WaitingServiceWorkerController | null = null;
const listeners = new Set<UpdateListener>();

/** Preserva o evento mesmo quando o worker fica waiting antes de o React montar. */
export function publishPwaUpdate(workbox: WaitingServiceWorkerController) {
  if (listeners.size === 0) {
    pendingUpdate = workbox;
    return;
  }

  listeners.forEach((listener) => listener(workbox));
}

export function subscribePwaUpdate(listener: UpdateListener) {
  listeners.add(listener);

  if (pendingUpdate) {
    const update = pendingUpdate;
    pendingUpdate = null;
    listener(update);
  }

  return () => {
    listeners.delete(listener);
  };
}

/** Ativa a versão em espera e só recarrega quando ela controlar a página. */
export function activateWaitingServiceWorker(
  workbox: WaitingServiceWorkerController,
  reload: () => void = () => window.location.reload(),
) {
  workbox.addEventListener("controlling", reload, { once: true });
  if (workbox.waiting) {
    workbox.waiting.postMessage({ type: "SKIP_WAITING" });
  } else {
    workbox.messageSW?.({ type: "SKIP_WAITING" });
  }
}

/**
 * Verifica uma versão nova antes do primeiro render e volta a verificar quando
 * o WebAPK regressa ao primeiro plano ou recupera rede.
 */
export async function startPwaUpdateLifecycle(
  workbox: DriverWorkboxController,
  runtime: PwaUpdateRuntime,
) {
  const hadControllerAtStartup = runtime.hasController();
  let checkingStartup = true;
  let waitingDuringStartup = false;

  workbox.addEventListener("waiting", () => {
    if (checkingStartup) {
      waitingDuringStartup = true;
      return;
    }
    publishPwaUpdate(workbox);
  });

  let registration: PwaRegistration | undefined;
  const checkForUpdate = () => {
    if (!runtime.isOnline() || !runtime.isVisible() || !registration) return;
    void registration.update().catch(() => undefined);
  };
  const subscribeToUpdateChecks = () => {
    const unsubscribeVisibility = runtime.subscribe(
      "visibilitychange",
      checkForUpdate,
    );
    const unsubscribeOnline = runtime.subscribe("online", checkForUpdate);
    return () => {
      unsubscribeVisibility();
      unsubscribeOnline();
    };
  };

  if (!hadControllerAtStartup) {
    checkingStartup = false;
    void workbox
      .register()
      .then((result) => {
        registration = result;
      })
      .catch(() => undefined);
    return { shouldRender: true, dispose: subscribeToUpdateChecks() };
  }

  try {
    registration = await workbox.register();
    await registration?.update();
  } catch {
    // Cold start offline must continue from the already certified cache.
  }

  const hasWaitingVersion =
    hadControllerAtStartup &&
    (waitingDuringStartup ||
      Boolean(workbox.waiting) ||
      Boolean(registration?.waiting));
  checkingStartup = false;

  if (hasWaitingVersion) {
    activateWaitingServiceWorker(workbox, runtime.reload);
    return { shouldRender: false, dispose: () => undefined };
  }

  return {
    shouldRender: true,
    dispose: subscribeToUpdateChecks(),
  };
}
