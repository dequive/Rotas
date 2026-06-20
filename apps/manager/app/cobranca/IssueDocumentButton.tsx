"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { issueBillingDocument } from "./actions";

export function IssueDocumentButton({ documentId }: { documentId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleIssue = async () => {
    setLoading(true);
    setError(null);
    const result = await issueBillingDocument(documentId);
    if (result.ok) {
      router.refresh();
    } else {
      setError(result.error);
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleIssue}
        disabled={loading}
        style={{ backgroundColor: loading ? "#d97706" : "#f59e0b" }}
        className="text-xs font-semibold text-[#0f1623] rounded px-3 py-1 whitespace-nowrap transition-colors duration-75 disabled:opacity-60 hover:opacity-90"
      >
        {loading ? "A emitir..." : "Emitir"}
      </button>
      {error && (
        <span className="text-[11px] text-error max-w-[160px] text-right leading-tight">
          {error}
        </span>
      )}
    </div>
  );
}
