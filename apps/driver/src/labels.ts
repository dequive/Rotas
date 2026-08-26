/**
 * Rótulos apresentados ao motorista.
 *
 * Regra da persona: a PWA nunca mostra um código interno do backend. Todo o
 * valor técnico que chega da API — estado da viagem, tipo de documento, padrão
 * de carga, estado da fila de sincronização — passa por aqui antes de ser
 * apresentado. Valores desconhecidos não são improvisados a partir do código:
 * a interface usa um rótulo português seguro e mantém o código apenas nos
 * dados técnicos/telemetria.
 */

/** Humaniza um código sem o deixar em snake_case nem em maiúsculas técnicas. */
export function humanizeCode(value: string, fallback = "—") {
  const words = value.replaceAll(/[_:-]+/g, " ").trim();
  if (!words) return fallback;
  return words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
}

function resolve(map: Record<string, string>, value: string | null | undefined, fallback = "—") {
  if (!value) return fallback;
  return map[value.trim().toLowerCase()] ?? fallback;
}

/** Vocabulário completo do lifecycle da viagem, tal como o backend o persiste. */
const TRIP_STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  planned: "Planeada",
  dispatch_pending: "A aguardar despacho",
  dispatched: "Despachada",
  in_progress: "Em curso",
  delayed: "Atrasada",
  incident: "Com incidente",
  arrived: "Chegada ao destino",
  delivered: "Entregue",
  closed: "Concluída",
  cancelled: "Cancelada",
};

export function tripStatusLabel(value: string | null | undefined) {
  return resolve(TRIP_STATUS_LABELS, value, "Estado por confirmar");
}

/** Padrão de carga da viagem (ida/volta). */
const LOAD_STATE_LABELS: Record<string, string> = {
  loaded_empty: "Ida carregada, volta vazia",
  loaded_loaded: "Ida e volta carregadas",
  empty_loaded: "Ida vazia, volta carregada",
  empty_empty: "Ida e volta vazias",
  loaded: "Carregada",
  empty: "Vazia",
};

export function loadStateLabel(value: string | null | undefined) {
  return resolve(LOAD_STATE_LABELS, value, "Carga por confirmar");
}

/**
 * Documentos de viagem. Cobre os tipos canónicos e as chaves de requisito no
 * formato `transport_document:<slug>` usadas pela política de despacho.
 */
const DOCUMENT_LABELS: Record<string, string> = {
  load_permit: "Autorização de carregamento (Load Permit)",
  cargo_manifest: "Manifesto de carga",
  transport_document: "Documento de transporte",
  guia_de_transporte: "Guia de transporte",
  transport_guide: "Guia de transporte",
  guia_remessa: "Guia de remessa",
  carta_porte_internacional: "Carta de porte internacional",
  dav: "DAV — Declaração de Aprovação de Viagem",
  declaracao_carga_perigosa: "Declaração de carga perigosa",
  delivery_proof: "Prova de descarga",
};

export function documentLabel(value: string) {
  const key = value.trim().toLowerCase();
  const bare = key.startsWith("transport_document:")
    ? key.slice("transport_document:".length).trim()
    : key;
  return DOCUMENT_LABELS[key] ?? DOCUMENT_LABELS[bare] ?? "Documento";
}

/** Entidades que a fila offline sincroniza. */
const SYNC_ENTITY_LABELS: Record<string, string> = {
  checklist: "Checklist",
  fuel_log: "Abastecimento",
  trip: "Viagem",
  trip_stop: "Paragem",
  trip_cost: "Custo de viagem",
  load_permit: "Autorização de carregamento (Load Permit)",
  cargo_manifest: "Manifesto de carga",
  transport_document: "Documento de transporte",
  delivery_proof: "Prova de descarga",
};

export function syncEntityLabel(value: string) {
  return resolve(SYNC_ENTITY_LABELS, value, "Registo");
}

/** Estados da fila offline. */
const SYNC_STATUS_LABELS: Record<string, string> = {
  local_only: "Guardado no telemóvel",
  syncing: "A sincronizar",
  synced: "Sincronizado",
  retrying: "A repetir envio",
  conflict: "Em conflito",
  failed: "Falhou",
  dead_letter: "Bloqueado — precisa de revisão",
};

export function syncStatusLabel(value: string) {
  return resolve(SYNC_STATUS_LABELS, value, "Estado desconhecido");
}
