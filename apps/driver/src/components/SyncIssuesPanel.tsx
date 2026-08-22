import { useCallback, useEffect, useState } from "react";
import {
  db,
  discardSyncItem,
  belongsToIdentity,
  getCurrentIdentityScope,
  requeueSyncItem,
  type SyncQueueItem,
} from "../db";

type SyncIssue = SyncQueueItem & { id: number };

interface SyncIssuesPanelProps {
  onChanged?: () => void;
}

export function SyncIssuesPanel({ onChanged }: SyncIssuesPanelProps) {
  const [issues, setIssues] = useState<SyncIssue[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadIssues = useCallback(async () => {
    const scope = getCurrentIdentityScope();
    if (!scope) {
      setIssues([]);
      return;
    }
    const items = await db.syncQueue
      .where("status")
      .anyOf(["conflict", "failed", "dead_letter"])
      .filter((item) => belongsToIdentity(item, scope))
      .toArray();
    setIssues(
      items
        .filter((item): item is SyncIssue => item.id !== undefined)
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
    );
  }, []);

  useEffect(() => {
    void loadIssues();
  }, [loadIssues]);

  async function retry(issue: SyncIssue) {
    setBusyId(issue.id);
    setMessage(null);
    try {
      await requeueSyncItem(issue.id);
      await loadIssues();
      onChanged?.();
    } catch {
      setMessage("Não foi possível reenfileirar o registo.");
    } finally {
      setBusyId(null);
    }
  }

  async function discard(issue: SyncIssue) {
    const confirmed = window.confirm(
      "Descartar este registo local e as evidências ainda não sincronizadas? Esta ação não pode ser anulada.",
    );
    if (!confirmed) return;
    setBusyId(issue.id);
    setMessage(null);
    try {
      await discardSyncItem(issue.id);
      await loadIssues();
      onChanged?.();
    } catch {
      setMessage("Não foi possível descartar o registo.");
    } finally {
      setBusyId(null);
    }
  }

  if (issues.length === 0 && !message) return null;

  return (
    <section className="sync-issues" aria-label="Registos com problemas de sincronização">
      <div className="sync-issues__header">
        <div>
          <p>Revisão necessária</p>
          <strong>{issues.length} registo(s) não sincronizado(s)</strong>
        </div>
      </div>
      {message && <p className="sync-issues__message" role="alert">{message}</p>}
      <div className="sync-issues__list">
        {issues.map((issue) => (
          <article className="sync-issue" key={issue.id}>
            <div>
              <strong>{issue.entityType.replaceAll("_", " ")}</strong>
              <span>{issue.status.replace("_", " ")}</span>
              <small>{issue.lastError ?? "Erro não especificado"}</small>
              <small>Tentativas: {issue.retryCount}/{5}</small>
            </div>
            <div className="sync-issue__actions">
              <button
                className="small-btn"
                disabled={busyId === issue.id}
                onClick={() => void retry(issue)}
                type="button"
              >
                Reenfileirar
              </button>
              <button
                className="small-btn sync-issue__discard"
                disabled={busyId === issue.id}
                onClick={() => void discard(issue)}
                type="button"
              >
                Descartar
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
