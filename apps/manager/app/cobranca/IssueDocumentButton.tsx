"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { issueBillingDocument } from "./actions";
import { Button } from "@/app/components/ui/Button";

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
      <Button size="sm" disabled={loading} onClick={handleIssue}>
        {loading ? "A emitir..." : "Emitir"}
      </Button>
      {error && (
        <span className="text-[11px] text-error max-w-[160px] text-right leading-tight">
          {error}
        </span>
      )}
    </div>
  );
}
