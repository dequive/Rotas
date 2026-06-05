import { useEffect, useState } from "react";

/**
 * useNetworkStatus — tracks browser online/offline state.
 * Uses navigator.onLine as initial value + listens for online/offline events.
 * Returns { isOnline: boolean }.
 */
export function useNetworkStatus(): { isOnline: boolean } {
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return { isOnline };
}
