import { ShieldAlert } from "lucide-react";

interface ForbiddenStateProps {
  /** What the user tried to see, in their words. */
  resource: string;
  /** Who does have access, so the user knows whom to ask. */
  grantedTo?: string;
}

/**
 * Shown when the API answers 403 for a surface the user reached.
 *
 * A permission refusal is not an empty result and must never be rendered as
 * one. "Nenhum registo encontrado" tells the user the data does not exist —
 * they close the page and act on a false belief. This tells them the data
 * exists, that they cannot see it, and who to ask.
 */
export function ForbiddenState({ resource, grantedTo }: ForbiddenStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-surface px-6 py-12 text-center"
      role="status"
    >
      <ShieldAlert className="h-8 w-8 text-amber" aria-hidden="true" />
      <div className="space-y-1">
        <p className="text-sm font-semibold text-ink">Sem permissão para ver {resource}</p>
        <p className="max-w-md text-xs text-muted">
          {grantedTo
            ? `Este conteúdo está reservado a ${grantedTo}. Peça acesso a quem administra a sua conta.`
            : "Peça acesso a quem administra a sua conta."}
        </p>
      </div>
    </div>
  );
}
