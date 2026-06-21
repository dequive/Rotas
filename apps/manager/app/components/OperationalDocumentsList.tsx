import { FileText, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OperationalDocument {
  id: string;
  document_type: string;
  document_number: string | null;
  issued_at: string | null;
  expiry_date: string | null;
  issuing_authority: string | null;
  verification_status: "pending" | "verified" | "rejected";
  notes: string | null;
  created_at: string;
}

interface Props {
  documents: OperationalDocument[];
  thirdPartyId?: string;
  subjectType?: string;
  subjectId?: string;
}

const VERIFICATION_BADGE: Record<
  string,
  { label: string; wrapperClass: string; dotClass: string; Icon: React.ElementType }
> = {
  pending: {
    label: "Pendente",
    wrapperClass: "bg-warning-bg text-warning",
    dotClass: "bg-amber",
    Icon: Clock,
  },
  verified: {
    label: "Verificado",
    wrapperClass: "bg-success-bg text-success",
    dotClass: "bg-success",
    Icon: CheckCircle,
  },
  rejected: {
    label: "Rejeitado",
    wrapperClass: "bg-error-bg text-error",
    dotClass: "bg-error",
    Icon: AlertTriangle,
  },
};

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  license: "Carta de Condução",
  passport: "Passaporte",
  bi: "Bilhete de Identidade",
  insurance: "Seguro",
  inspection: "Inspecção",
  contract_copy: "Cópia de Contrato",
  commercial_register: "Registo Comercial",
  nuit_certificate: "Certificado NUIT",
  other: "Outro",
};

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
}

export function OperationalDocumentsList({ documents }: Props) {
  return (
    <div>
      {documents.length === 0 ? (
        <div className="text-center py-8 text-[13px] text-muted">
          Sem documentos registados
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px] border-collapse">
            <thead>
              <tr className="border-b border-border">
                {["Tipo", "Número", "Emissão", "Validade", "Entidade", "Estado"].map((h, i) => (
                  <th
                    key={h}
                    className={cn(
                      "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted whitespace-nowrap",
                      i === 0 && "min-w-[160px]",
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => {
                const days = daysUntil(doc.expiry_date);
                const isExpiring = days !== null && days >= 0 && days <= 30;
                const isExpired = days !== null && days < 0;
                const badge =
                  VERIFICATION_BADGE[doc.verification_status] ?? VERIFICATION_BADGE.pending;
                const BadgeIcon = badge.Icon;

                return (
                  <tr key={doc.id} className="border-b border-border">
                    <td className="px-3 py-2.5 font-semibold text-ink whitespace-nowrap">
                      {DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs text-ink">
                      {doc.document_number ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs text-muted">
                      {doc.issued_at ?? "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      {doc.expiry_date ? (
                        <span
                          className={cn(
                            "font-mono text-xs tabular-nums",
                            isExpired
                              ? "text-error font-semibold"
                              : isExpiring
                                ? "text-warning font-semibold"
                                : "text-ink",
                          )}
                        >
                          {doc.expiry_date}
                          {isExpired && " (vencido)"}
                          {isExpiring && !isExpired && ` (${days}d)`}
                        </span>
                      ) : (
                        <span className="text-muted text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted">
                      {doc.issuing_authority ?? "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold",
                          badge.wrapperClass,
                        )}
                      >
                        <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", badge.dotClass)} />
                        <BadgeIcon size={10} />
                        {badge.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
