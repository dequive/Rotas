import { useEffect, useRef, useState } from "react";
import { belongsToIdentity, db, getCurrentIdentityScope } from "../db";
import {
  subscribePwaUpdate,
  type WaitingServiceWorkerController,
} from "../pwaUpdate";

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
  workboxInstance: WaitingServiceWorkerController | null;
}

/**
 * useSyncStatus — aggregates all banner state into a single state machine.
 * Listens to: navigator.onLine, Dexie syncQueue counts, custom window events
 * from api.ts (session-expired, driver-access-revoked, sw-update-available).
 */
export function useSyncStatus(
  isOnline: boolean,
  isSyncing: boolean,
  sessionId?: string,
): SyncStatusState {
  const [pendingCount, setPendingCount] = useState(0);
  const [errorCount, setErrorCount] = useState(0);
  const [sessionState, setSessionState] = useState<"ok" | "expired" | "revoked">("ok");
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const workboxRef = useRef<WaitingServiceWorkerController | null>(null);

  // A sessão é uma identidade efémera. Um novo emparelhamento não pode herdar
  // os estados terminalmente expirado/revogado da sessão anterior.
  useEffect(() => {
    setSessionState("ok");
  }, [sessionId]);

  // Poll Dexie syncQueue counts every 5 seconds when banner is visible
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    async function refresh() {
      try {
        const scope = getCurrentIdentityScope();
        if (!scope) {
          setPendingCount(0);
          setErrorCount(0);
          return;
        }
        const pending = await db.syncQueue
          .where("status")
          .anyOf(["local_only", "retrying"])
          .filter((item) => belongsToIdentity(item, scope))
          .count();
        const errors = await db.syncQueue
          .where("status")
          .anyOf(["conflict", "failed", "dead_letter"])
          .filter((item) => belongsToIdentity(item, scope))
          .count();
        setPendingCount(pending);
        setErrorCount(errors);
      } catch {
        // DB not available — ignore
      }
    }

    refresh();
    interval = setInterval(refresh, 5000);
    return () => { if (interval) clearInterval(interval); };
  }, []);

  // Listen for auth events dispatched by api.ts (AUTH-02 / D-08)
  useEffect(() => {
    const onSessionExpired = () => setSessionState("expired");
    const onAccessRevoked = () => setSessionState("revoked");
    const onUpdateAvailable = (workbox: WaitingServiceWorkerController) => {
      workboxRef.current = workbox;
      setUpdateAvailable(true);
    };

    window.addEventListener("session-expired", onSessionExpired);
    window.addEventListener("driver-access-revoked", onAccessRevoked);
    const unsubscribePwaUpdate = subscribePwaUpdate(onUpdateAvailable);

    return () => {
      window.removeEventListener("session-expired", onSessionExpired);
      window.removeEventListener("driver-access-revoked", onAccessRevoked);
      unsubscribePwaUpdate();
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
