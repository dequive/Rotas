import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  LockKeyhole,
  MapPinned,
  Send,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  downloadDriverTripDocument,
  getDriverTripDocuments,
  listDriverTripHistory,
  listDriverTrips,
  requestDriverTripDocument,
  type DriverTrip,
  type DriverTripDocuments,
} from "../api";

type TripsViewProps = {
  mode: "assigned" | "history";
  onBack: () => void;
};

const DOCUMENT_LABELS: Record<string, string> = {
  load_permit: "Load Permit",
  cargo_manifest: "Manifesto de carga",
  transport_document: "Documento de transporte",
  "transport_document:guia_de_transporte": "Guia de transporte",
  "transport_document:guia_remessa": "Guia de remessa",
  "transport_document:carta_porte_internacional": "Carta de porte internacional",
  "transport_document:dav": "DAV — Declaração de Aprovação de Viagem",
  "transport_document:declaracao_carga_perigosa": "Declaração de carga perigosa",
};

function documentLabel(value: string) {
  return DOCUMENT_LABELS[value] ?? value.replaceAll("_", " ");
}

function dateLabel(value: string | null) {
  if (!value) return "Horário por confirmar";
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    approved: "Aprovada",
    assigned: "Atribuída",
    planned: "Planeada",
    dispatched: "Despachada",
    in_progress: "Em curso",
    pending_delivery_proof: "A aguardar prova de descarga",
    pending_delivery_validation: "A aguardar validação",
    closed: "Concluída",
    cancelled: "Cancelada",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

export function TripsView({ mode, onBack }: TripsViewProps) {
  const [trips, setTrips] = useState<DriverTrip[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedTrip, setSelectedTrip] = useState<DriverTrip | null>(null);
  const [documents, setDocuments] = useState<DriverTripDocuments | null>(null);
  const [state, setState] = useState<"loading" | "success" | "error">("loading");
  const [documentState, setDocumentState] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [actionMessage, setActionMessage] = useState("");
  const [requesting, setRequesting] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const loadTrips = useCallback(async (offset = 0) => {
    if (offset === 0) {
      setState("loading");
      setSelectedTrip(null);
      setDocuments(null);
    } else {
      setLoadingMore(true);
    }
    try {
      const page = mode === "history"
        ? await listDriverTripHistory(20, offset)
        : await listDriverTrips(20, offset);
      setTrips((current) => offset === 0 ? page.items : [...current, ...page.items]);
      setTotal(page.total);
      setState("success");
    } catch {
      if (offset === 0) {
        setTrips([]);
        setTotal(0);
        setState("error");
      }
    } finally {
      setLoadingMore(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadTrips();
  }, [loadTrips]);

  async function openTrip(trip: DriverTrip) {
    setSelectedTrip(trip);
    setDocuments(null);
    setDocumentState("loading");
    setActionMessage("");
    try {
      setDocuments(await getDriverTripDocuments(trip.id));
      setDocumentState("success");
    } catch {
      setDocumentState("error");
    }
  }

  async function requestDocument(documentType: string) {
    if (!selectedTrip) return;
    setRequesting(documentType);
    setActionMessage("");
    try {
      await requestDriverTripDocument(selectedTrip.id, documentType);
      setDocuments(await getDriverTripDocuments(selectedTrip.id));
      setActionMessage("Pedido enviado ao gestor de frota.");
    } catch {
      setActionMessage("Não foi possível enviar o pedido. Tente novamente.");
    } finally {
      setRequesting(null);
    }
  }

  async function downloadDocument(fileId: string, filename: string) {
    if (!selectedTrip) return;
    setDownloading(fileId);
    setActionMessage("");
    try {
      const blob = await downloadDriverTripDocument(selectedTrip.id, fileId);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setActionMessage("Não foi possível abrir o documento. Tente novamente.");
    } finally {
      setDownloading(null);
    }
  }

  if (selectedTrip) {
    const activeRequestTypes = new Set(
      documents?.requests
        .filter((request) => request.status === "open" || request.status === "acknowledged")
        .map((request) => request.document_type) ?? [],
    );
    return (
      <section className="trip-workspace" aria-labelledby="trip-detail-title">
        <button className="back-btn trip-back" type="button" onClick={() => setSelectedTrip(null)}>
          <ArrowLeft size={18} /> {mode === "history" ? "Histórico" : "Minhas viagens"}
        </button>
        <header className="trip-detail-header">
          <span>{selectedTrip.status === "closed" ? "Viagem concluída" : "Viagem atribuída"}</span>
          <h2 id="trip-detail-title">{selectedTrip.origin} → {selectedTrip.destination}</h2>
          <p>{dateLabel(selectedTrip.planned_departure)}</p>
        </header>

        <dl className="trip-facts">
          <div><dt>Estado</dt><dd>{statusLabel(selectedTrip.status)}</dd></div>
          <div><dt>Carga</dt><dd>{selectedTrip.cargo_type ?? "Não informada"}</dd></div>
          <div><dt>Peso</dt><dd>{selectedTrip.cargo_weight ? `${selectedTrip.cargo_weight} kg` : "—"}</dd></div>
          <div><dt>Destinatário</dt><dd>{selectedTrip.recipient_name ?? "—"}</dd></div>
        </dl>

        <section className="document-panel" aria-labelledby="documents-title">
          <div className="document-panel__title">
            <div>
              <span>Preparação da viagem</span>
              <h3 id="documents-title">Documentos</h3>
            </div>
            {documents?.complete ? <CheckCircle2 className="success-icon" /> : null}
          </div>

          {documentState === "loading" && <p role="status">A verificar documentos…</p>}
          {documentState === "error" && (
            <div className="inline-state inline-state--error" role="alert">
              <AlertTriangle size={18} />
              <span>Não foi possível carregar os documentos.</span>
              <button type="button" onClick={() => void openTrip(selectedTrip)}>Tentar novamente</button>
            </div>
          )}
          {documentState === "success" && documents && (
            <>
              <div className={`document-summary ${documents.complete ? "is-complete" : "is-missing"}`}>
                {documents.complete ? (
                  <><CheckCircle2 size={18} /><strong>Documentação completa</strong></>
                ) : (
                  <><AlertTriangle size={18} /><strong>Documentação incompleta</strong></>
                )}
              </div>

              {!documents.can_request && (
                <p className="read-only-note"><LockKeyhole size={17} /> Viagem fechada — somente leitura.</p>
              )}

              <div className="requirements-list" aria-label="Requisitos documentais">
                {documents.requirements.map((requirement) => (
                  <article key={requirement.document_type} className="requirement-row">
                    <span className={requirement.present ? "requirement-dot present" : "requirement-dot missing"} />
                    <div>
                      <strong>{documentLabel(requirement.document_type)}</strong>
                      <small>{requirement.present ? "Disponível" : "Em falta"}</small>
                    </div>
                    {!requirement.present && documents.can_request && activeRequestTypes.has(requirement.document_type) && (
                      <span className="request-pending">Pedido enviado</span>
                    )}
                    {!requirement.present && documents.can_request && !activeRequestTypes.has(requirement.document_type) && (
                      <button
                        type="button"
                        disabled={requesting !== null}
                        onClick={() => void requestDocument(requirement.document_type)}
                        aria-label={`Solicitar ${documentLabel(requirement.document_type)}`}
                      >
                        <Send size={15} /> {requesting === requirement.document_type ? "A enviar…" : "Solicitar"}
                      </button>
                    )}
                  </article>
                ))}
              </div>

              <div className="issued-documents">
                <h4>Documentos emitidos</h4>
                {documents.documents.length === 0 ? (
                  <p>Nenhum documento foi disponibilizado.</p>
                ) : documents.documents.map((document) => (
                  <article key={document.id} className="issued-document">
                    <FileText size={19} />
                    <div>
                      <strong>{documentLabel(document.document_type)}</strong>
                      <small>{document.document_number ?? "Sem número"}</small>
                    </div>
                    {document.file_id ? (
                      <button
                        type="button"
                        onClick={() => void downloadDocument(
                          document.file_id!,
                          `${document.document_number ?? document.document_type}.pdf`,
                        )}
                        disabled={downloading === document.file_id}
                        aria-label={`Abrir ${documentLabel(document.document_type)}`}
                      >
                        <Download size={16} />
                      </button>
                    ) : <span className="digital-only">Registo digital</span>}
                  </article>
                ))}
              </div>
              {actionMessage && <p className="action-message" role="status">{actionMessage}</p>}
            </>
          )}
        </section>
      </section>
    );
  }

  return (
    <section className="trip-workspace" aria-labelledby="trip-list-title">
      <button className="back-btn trip-back" type="button" onClick={onBack}>
        <ArrowLeft size={18} /> Hoje
      </button>
      <header className="workspace-heading">
        <span>{mode === "history" ? "Arquivo operacional" : "Trabalho atribuído"}</span>
        <h2 id="trip-list-title">{mode === "history" ? "Histórico" : "Minhas viagens"}</h2>
        <p>{mode === "history" ? "Viagens concluídas e canceladas." : "Viagens planeadas para si pelo gestor de frota."}</p>
      </header>

      {state === "loading" && <div className="panel inline-state" role="status">A carregar viagens…</div>}
      {state === "error" && (
        <div className="panel inline-state inline-state--error" role="alert">
          <AlertTriangle size={20} />
          <span>Não foi possível carregar as viagens.</span>
          <button type="button" onClick={() => void loadTrips()}>Tentar novamente</button>
        </div>
      )}
      {state === "success" && trips.length === 0 && (
        <div className="panel trip-empty">
          <MapPinned size={28} />
          <h3>{mode === "history" ? "Ainda não há histórico" : "Sem viagens atribuídas"}</h3>
          <p>{mode === "history" ? "As viagens fechadas aparecerão aqui." : "O gestor de frota ainda não lhe atribuiu uma viagem."}</p>
        </div>
      )}
      {state === "success" && trips.length > 0 && (
        <div className="trip-list">
          {trips.map((trip) => (
            <button
              key={trip.id}
              type="button"
              className="trip-list-card"
              onClick={() => void openTrip(trip)}
              aria-label={`${trip.origin} para ${trip.destination}`}
            >
              <span className="trip-list-card__route">{trip.origin} → {trip.destination}</span>
              <span className="trip-list-card__meta">{dateLabel(trip.planned_departure)}</span>
              <span className="trip-list-card__status">{statusLabel(trip.status)}</span>
            </button>
          ))}
          {trips.length < total && (
            <button
              type="button"
              className="load-more"
              disabled={loadingMore}
              onClick={() => void loadTrips(trips.length)}
            >
              {loadingMore ? "A carregar…" : `Carregar mais (${trips.length} de ${total})`}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
