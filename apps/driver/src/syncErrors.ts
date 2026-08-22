/**
 * Turns a sync `error_code` into something a driver can act on.
 *
 * The server reports failures per operation with a stable code and a technical
 * message. The message is written for an engineer reading a log — English,
 * snake_case field names — and is the wrong thing to put in front of a driver
 * holding a phone at a weighbridge.
 *
 * The distinction that matters most here is not the wording: it is whether
 * retrying can ever work. Offering "Reenfileirar" for a payload the server will
 * reject identically every time is a false affordance — the driver taps it,
 * waits, and the record fails again with no new information.
 */

export type SyncFailureKind = "retryable" | "permanent" | "conflict";

export interface SyncFailureExplanation {
  /** What the driver reads. Portuguese, no jargon, says what to do next. */
  message: string;
  kind: SyncFailureKind;
  /** Whether re-queueing this record has any chance of succeeding. */
  canRetry: boolean;
}

const EXPLANATIONS: Record<string, SyncFailureExplanation> = {
  payload_validation_failed: {
    message:
      "Este registo está incompleto e o servidor não o aceita. Reenviar não resolve — registe de novo ou descarte.",
    kind: "permanent",
    canRetry: false,
  },
  server_id_required: {
    message:
      "Esta alteração perdeu a ligação ao registo original. Registe de novo em vez de reenviar.",
    kind: "permanent",
    canRetry: false,
  },
  idempotency_key_reused: {
    message:
      "Já existe um registo enviado com estes dados e uma versão diferente. Confirme com o gestor qual fica válida.",
    kind: "conflict",
    canRetry: false,
  },
  idempotency_race_conflict: {
    message: "O registo foi enviado ao mesmo tempo por outro dispositivo. Reenvie para confirmar.",
    kind: "conflict",
    canRetry: true,
  },
  session_expired: {
    message: "A sessão expirou. Volte a entrar e o registo é enviado sozinho.",
    kind: "retryable",
    canRetry: true,
  },
  driver_access_revoked: {
    message: "O acesso deste dispositivo foi revogado. Contacte o gestor.",
    kind: "permanent",
    canRetry: false,
  },
  sync_operation_failed: {
    message: "O servidor não conseguiu processar este registo. Tente reenviar mais tarde.",
    kind: "retryable",
    canRetry: true,
  },
  update_failed: {
    message: "Não foi possível aplicar esta alteração. Tente reenviar mais tarde.",
    kind: "retryable",
    canRetry: true,
  },
  unsupported_entity_type_for_update: {
    message: "Esta app está desactualizada para enviar esta alteração. Actualize a aplicação.",
    kind: "permanent",
    canRetry: false,
  },
  vehicle_not_found: {
    message: "A viatura deste registo já não existe. Confirme com o gestor.",
    kind: "permanent",
    canRetry: false,
  },
  trip_not_found: {
    message: "A viagem deste registo já não existe. Confirme com o gestor.",
    kind: "permanent",
    canRetry: false,
  },
};

/** Fallback for a code this build does not know — the server may be ahead of the app. */
const UNKNOWN: SyncFailureExplanation = {
  message: "Este registo não foi aceite. Tente reenviar; se persistir, contacte o gestor.",
  kind: "retryable",
  canRetry: true,
};

export function explainSyncFailure(errorCode?: string): SyncFailureExplanation {
  if (!errorCode) return UNKNOWN;
  return EXPLANATIONS[errorCode] ?? UNKNOWN;
}

export function isKnownSyncErrorCode(errorCode: string): boolean {
  return errorCode in EXPLANATIONS;
}
