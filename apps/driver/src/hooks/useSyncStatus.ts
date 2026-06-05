import { useEffect, useRef, useState } from "react";
import { db } from "../db";

export type BannerState =
  | "idle"
  | "offline"
  | "syncing"
  | "error"
  | "session_expired"
  | "access_revoked"
  | "update_available";

export interface SyncStatusState {
  bannerState: BannerState;
  pendingCount: number;
  errorCount: number;
  // Workbox instance for triggering SKIP_WAITING — only set in update_available state
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  workboxInstance: any | null;
}

/**
 * useSyncStatus — aggregates all banner state into a single state machine.
 * Listens to: navigator.onLine, Dexie syncQueue counts, custom window events
 * from api.ts (session-expired, driver-access-revoked, sw-update-available).
 */
export function useSyncStatus(isOnline: boolean, isSyncing: boolean): SyncStatusState {
  const [pendingCount, setPendingCount] = useState(0);
  const [errorCount, setErrorCount] = useState(0);
  const [sessionState, setSessionState] = useState<"ok" | "expired" | "revoked">("ok");
  const [updateAvailable, setUpdateAvailable] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const workboxRef = useRef<any | null>(null);

  // Poll Dexie syncQueue counts every 5 seconds when banner is visible
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    async function refresh() {
      try {
        const pending = await db.syncQueue
          .where("status")
          .anyOf(["local_only", "retrying"])
          .count();
        const errors = await db.syncQueue
          .where("status")
          .equals("conflict")
          .count();
        setPendingCount(pending);
        setErrorCount(errors);
      } catch {
        // DB not available — ignore
      }
    }

    void refresh();
    interval = setInterval(() => { void refresh(); }, 5000);
    return () => { if (interval) clearInterval(interval); };
  }, []);

  // Listen for auth events dispatched by api.ts (AUTH-02 / D-08)
  useEffect(() => {
    const onSessionExpired = () => setSessionState("expired");
    const onAccessRevoked = () => setSessionState("revoked");
    const onUpdateAvailable = (e: Event) => {
      const customEvent = e as CustomEvent;
      workboxRef.current = customEvent.detail?.wb ?? null;
      setUpdateAvailable(true);
    };

    window.addEventListener("session-expired", onSessionExpired);
    window.addEventListener("driver-access-revoked", onAccessRevoked);
    window.addEventListener("sw-update-available", onUpdateAvailable);

    return () => {
      window.removeEventListener("session-expired", onSessionExpired);
      window.removeEventListener("driver-access-revoked", onAccessRevoked);
      window.removeEventListener("sw-update-available", onUpdateAvailable);
    };
  }, []);

  // Derive banner state from all signals
  // Priority order (highest first): access_revoked > session_expired > offline > syncing > error > update_available > idle
  let bannerState: BannerState = "idle";

  if (sessionState === "revoked") {
    bannerState = "access_revoked";
  } else if (sessionState === "expired") {
    bannerState = "session_expired";
  } else if (!isOnline) {
    bannerState = "offline";
  } else if (isSyncing) {
    bannerState = "syncing";
  } else if (errorCount > 0) {
    bannerState = "error";
  } else if (updateAvailable) {
    bannerState = "update_available";
  }

  return {
    bannerState,
    pendingCount,
    errorCount,
    workboxInstance: workboxRef.current,
  };
}
