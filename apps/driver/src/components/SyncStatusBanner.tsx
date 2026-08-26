import { useState } from "react";
import { BannerState, SyncStatusState } from "../hooks/useSyncStatus";
import {
  activateWaitingServiceWorker,
  type WaitingServiceWorkerController,
} from "../pwaUpdate";

export { activateWaitingServiceWorker } from "../pwaUpdate";

interface SyncStatusBannerProps {
  status: SyncStatusState;
  onRePair?: () => void;
}

/**
 * SyncStatusBanner — ambient status indicator for the driver PWA.
 *
 * Covers 7 states per UI-SPEC.md (Phase 2):
 * - idle: hidden (display: none via CSS [data-state="idle"])
 * - offline: orange — "Sem ligação — a gravar localmente · X registos pendentes"
 * - syncing: green — "A sincronizar... · X registos pendentes"
 * - error: red — "X registos com erro — contacta o gestor"
 * - session_expired: "Sessão expirada — contacta o teu gestor para re-parear o dispositivo"
 * - access_revoked: "Acesso revogado. Os teus registos locais foram preservados — contacta o teu gestor."
 * - update_available: blue — "Nova versão disponível" + "Verificar atualizações" button
 *
 * Always mounted at the bottom of .phone-shell (margin-top: auto in CSS).
 * Never unmounts — only visually hidden via display:none in idle state.
 */
export function SyncStatusBanner({ status, onRePair }: SyncStatusBannerProps) {
  const { bannerState, pendingCount, errorCount, workboxInstance } = status;
  const [confirmRePair, setConfirmRePair] = useState(false);

  function getModifierClass(state: BannerState): string {
    switch (state) {
      case "offline": return "sync-banner--offline";
      case "syncing": return "sync-banner--syncing";
      case "error": return "sync-banner--error";
      case "session_expired": return "sync-banner--session-expired";
      case "access_revoked": return "sync-banner--access-revoked";
      case "update_available": return "sync-banner--update";
      default: return "";
    }
  }

  function getMessage(): string {
    switch (bannerState) {
      case "offline":
        return `Sem ligação — a gravar localmente${pendingCount > 0 ? ` · ${pendingCount === 1 ? "1 registo pendente" : `${pendingCount} registos pendentes`}` : ""}`;
      case "syncing":
        return `A sincronizar...${pendingCount > 0 ? ` · ${pendingCount === 1 ? "1 registo pendente" : `${pendingCount} registos pendentes`}` : ""}`;
      case "error":
        return errorCount === 1
          ? "1 registo precisa de revisão — contacte o gestor"
          : `${errorCount} registos precisam de revisão — contacte o gestor`;
      case "session_expired":
        return "Sessão expirada — contacte o gestor para voltar a emparelhar o dispositivo";
      case "access_revoked":
        return "Acesso revogado. Os registos locais foram preservados — contacte o gestor.";
      case "update_available":
        return "Nova versão disponível";
      default:
        return "";
    }
  }

  function handleUpdate() {
    if (workboxInstance) activateWaitingServiceWorker(workboxInstance);
  }

  const modifierClass = getModifierClass(bannerState);

  return (
    <div
      className={`sync-banner${modifierClass ? ` ${modifierClass}` : ""}`}
      data-state={bannerState}
      role="status"
      aria-live="polite"
      aria-label="Estado de sincronização"
    >
      <span className="sync-banner__message">{getMessage()}</span>
      {bannerState === "session_expired" && onRePair && !confirmRePair && (
        <span className="sync-banner__action">
          <button className="small-btn" onClick={() => setConfirmRePair(true)} type="button">
            Voltar a emparelhar
          </button>
        </span>
      )}
      {bannerState === "session_expired" && onRePair && confirmRePair && (
        <div className="sync-banner__confirm" role="alert">
          <span>
            Confirme com o gestor que os registos pendentes foram tratados. Os
            dados locais desta sessão serão removidos.
          </span>
          <span className="sync-banner__confirm-actions">
            <button className="small-btn" onClick={() => setConfirmRePair(false)} type="button">
              Cancelar
            </button>
            <button className="small-btn" onClick={onRePair} type="button">
              Limpar e emparelhar
            </button>
          </span>
        </div>
      )}
      {bannerState === "update_available" && (
        <span className="sync-banner__action">
          <button className="small-btn" onClick={handleUpdate} type="button">
            Verificar atualizações
          </button>
        </span>
      )}
    </div>
  );
}
