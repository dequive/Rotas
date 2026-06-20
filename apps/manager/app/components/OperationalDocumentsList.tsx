import { FileText, AlertTriangle, CheckCircle, Clock } from "lucide-react";

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
  { label: string; dotColor: string; textColor: string; bgColor: string; Icon: React.ElementType }
> = {
  pending: {
    label: "Pendente",
    dotColor: "#f59e0b",
    textColor: "var(--warning, #f59e0b)",
    bgColor: "rgba(245,158,11,0.10)",
    Icon: Clock,
  },
  verified: {
    label: "Verificado",
    dotColor: "#22c55e",
    textColor: "var(--success, #22c55e)",
    bgColor: "rgba(34,197,94,0.10)",
    Icon: CheckCircle,
  },
  rejected: {
    label: "Rejeitado",
    dotColor: "#ef4444",
    textColor: "var(--error, #ef4444)",
    bgColor: "rgba(239,68,68,0.10)",
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
        <div
          style={{
            textAlign: "center",
            padding: "32px 16px",
            fontSize: "13px",
            color: "var(--muted)",
            fontFamily: "Manrope, sans-serif",
          }}
        >
          Sem documentos registados
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13px",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Tipo", "Número", "Emissão", "Validade", "Entidade", "Estado"].map((h, i) => (
                  <th
                    key={h}
                    style={{
                      padding: "8px 12px",
                      textAlign: "left",
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase" as const,
                      letterSpacing: "0.05em",
                      color: "var(--muted)",
                      whiteSpace: "nowrap" as const,
                      minWidth: i === 0 ? 160 : undefined,
                    }}
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
                  <tr key={doc.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td
                      style={{
                        padding: "10px 12px",
                        fontWeight: 600,
                        color: "var(--ink)",
                        whiteSpace: "nowrap" as const,
                      }}
                    >
                      {DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                    </td>
                    <td
                      style={{
                        padding: "10px 12px",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "12px",
                        color: "var(--ink)",
                      }}
                    >
                      {doc.document_number ?? "—"}
                    </td>
                    <td
                      style={{
                        padding: "10px 12px",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "12px",
                        color: "var(--muted)",
                      }}
                    >
                      {doc.issued_at ?? "—"}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      {doc.expiry_date ? (
                        <span
                          style={{
                            fontFamily: "IBM Plex Mono, monospace",
                            fontSize: "12px",
                            fontWeight: isExpired || isExpiring ? 600 : 400,
                            color: isExpired
                              ? "var(--error, #ef4444)"
                              : isExpiring
                                ? "var(--warning, #f59e0b)"
                                : "var(--ink)",
                          }}
                        >
                          {doc.expiry_date}
                          {isExpired && " (vencido)"}
                          {isExpiring && !isExpired && ` (${days}d)`}
                        </span>
                      ) : (
                        <span style={{ color: "var(--muted)", fontSize: "12px" }}>—</span>
                      )}
                    </td>
                    <td
                      style={{
                        padding: "10px 12px",
                        fontSize: "12px",
                        color: "var(--muted)",
                      }}
                    >
                      {doc.issuing_authority ?? "—"}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "2px 8px",
                          borderRadius: 999,
                          fontSize: "11px",
                          fontWeight: 600,
                          background: badge.bgColor,
                          color: badge.textColor,
                          fontFamily: "Manrope, sans-serif",
                        }}
                      >
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: badge.dotColor,
                            flexShrink: 0,
                          }}
                        />
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
