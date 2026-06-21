/**
 * LimitWarningBanner — persistent plan limit warning for manager layout.
 *
 * Rules (INFRA-03 / D-17):
 * - Shows when any dimension is >= 80% of its limit
 * - Amber background at 80–99%, red (destructive) at >= 100%
 * - Shows the single worst dimension (highest pct) to avoid noise
 * - Not dismissible — persists until usage drops or tenant upgrades
 * - No banner when all max values are null (unlimited plan)
 *
 * Design tokens (DESIGN.md):
 * - Warning state: --amber #f59e0b → Tailwind amber-400/amber-950
 * - Error state: --error #dc2626 → Tailwind red-600/white
 * - Font: Manrope (UI text), IBM Plex Mono (numeric used/max values)
 * - Badge dot: inline span (DESIGN.md convention — ::before not usable in JSX)
 * - Decoration: minimal — no gradients, no blobs
 */

interface DimensionLimit {
  used: number;
  max: number | null;
  pct: number | null;
}

export interface TenantLimits {
  vehicles: DimensionLimit;
  drivers: DimensionLimit;
  users: DimensionLimit;
  upgrade_url: string;
}

interface LimitWarningBannerProps {
  limits: TenantLimits | null;
}

const DIMENSION_LABELS: Record<"vehicles" | "drivers" | "users", string> = {
  vehicles: "Veículos",
  drivers: "Motoristas",
  users: "Utilizadores",
};

/**
 * pct from the API is 0–100 (e.g. 80.0 = 80%).
 * Thresholds: warning at pct >= 80, critical at pct >= 100.
 */
const WARNING_THRESHOLD = 80;
const CRITICAL_THRESHOLD = 100;

export function LimitWarningBanner({ limits }: LimitWarningBannerProps) {
  if (!limits) return null;

  // Find the worst dimension (highest pct that is >= warning threshold)
  const candidates = (["vehicles", "drivers", "users"] as const)
    .map((key) => ({ key, ...limits[key] }))
    .filter((d) => d.pct !== null && d.pct >= WARNING_THRESHOLD)
    .sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0));

  if (candidates.length === 0) return null;

  const worst = candidates[0];
  const isAtLimit = (worst.pct ?? 0) >= CRITICAL_THRESHOLD;
  const label = DIMENSION_LABELS[worst.key];

  // Amber at 80–99% (--amber / amber-400 + amber-950 text), red at 100%+ (--error / red-600 + white)
  const bgClass = isAtLimit
    ? "bg-red-600 text-white"
    : "bg-amber-400 text-amber-950";

  const dotClass = isAtLimit ? "bg-white" : "bg-amber-dark";

  const linkClass = isAtLimit
    ? "text-white underline font-semibold hover:opacity-80 transition-opacity flex-shrink-0"
    : "text-amber-900 underline font-semibold hover:opacity-80 transition-opacity flex-shrink-0";

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
        Limite de {label}:{" "}
        <span className="font-mono">
          {worst.used}/{worst.max ?? "∞"}
        </span>{" "}
        utilizados.
      </span>

      {limits.upgrade_url ? (
        <a
          href={limits.upgrade_url}
          target="_blank"
          rel="noopener noreferrer"
          className={linkClass}
        >
          Fazer upgrade &rarr;
        </a>
      ) : null}
    </div>
  );
}
