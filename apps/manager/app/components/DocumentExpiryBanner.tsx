/**
 * DocumentExpiryBanner — persistent document expiry warning for manager layout.
 *
 * Rules:
 * - Amber banner: 1+ documents expiring in 8–30 days
 * - Red banner: 1+ documents expiring in ≤7 days (critical)
 * - Shows count of affected documents
 * - Not dismissible — persists until documents are renewed
 * - No banner when list is empty or fetch fails (returns null)
 *
 * Design tokens (DESIGN.md):
 * - Warning state: semantic warning tokens
 * - Error state: semantic error tokens
 * - Font: Manrope (UI text), IBM Plex Mono (numeric count)
 * - Badge dot: inline span (DESIGN.md convention — ::before not usable in JSX)
 * - Decoration: minimal — no gradients, no blobs
 */

export interface ExpiryAlert {
  entity_type: string;
  entity_id: string;
  entity_name: string;
  document_type: string;
  expires_at: string;
  days_remaining: number;
  severity: "critical" | "urgent" | "warning";
}

interface DocumentExpiryBannerProps {
  alerts: ExpiryAlert[];
}

const CRITICAL_DAYS = 7;

export function DocumentExpiryBanner({ alerts }: DocumentExpiryBannerProps) {
  if (!alerts || alerts.length === 0) return null;

  const hasCritical = alerts.some((a) => a.days_remaining <= CRITICAL_DAYS);
  const count = alerts.length;

  // Amber at 8–30 days (--amber / amber-400 + amber-950 text), red at ≤7 days (--error / red-600 + white)
  const bgClass = hasCritical
    ? "bg-error text-white"
    : "bg-amber text-ink";

  const dotClass = hasCritical ? "bg-white" : "bg-amber-dark";

  const linkClass = hasCritical
    ? "text-white underline font-semibold hover:opacity-80 transition-opacity flex-shrink-0"
    : "text-ink underline font-semibold hover:opacity-80 transition-opacity flex-shrink-0";

  const urgencyLabel = hasCritical
    ? "crítico — renovar imediatamente"
    : "verificar em breve";

  return (
    <div
      className={`w-full px-4 py-2 text-sm font-medium flex items-center justify-center gap-3 ${bgClass}`}
      role="alert"
      aria-live="polite"
    >
      {/* Colored dot — DESIGN.md badge convention (inline span, not ::before pseudo-element) */}
      <span
        className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`}
        aria-hidden="true"
      />

      <span>
        <span className="font-mono">{count}</span>{" "}
        documento{count !== 1 ? "s" : ""} a expirar —{" "}
        <span className="font-semibold">{urgencyLabel}</span>.
      </span>

      <a href="/frota/motoristas" className={linkClass}>
        Ver documentos &rarr;
      </a>
    </div>
  );
}
