import { HttpContractError } from "@rotas/http-contract";
import { AlertTriangle, CheckCircle2, Fuel, ReceiptText, WalletCards } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  listDriverAdvanceRecords,
  listDriverChecklistRecords,
  listDriverExpenseRecords,
  listDriverFuelRecords,
  type DriverAdvanceRecord,
  type DriverChecklistRecord,
  type DriverExpenseRecord,
  type DriverFuelRecord,
} from "../api";
import {
  getCurrentIdentityScope,
  getDriverReadCache,
  saveDriverReadCache,
} from "../db";

type RecordKind = "checklist" | "fuel" | "expense" | "advance";
type JournalItem =
  | { kind: "checklist"; record: DriverChecklistRecord }
  | { kind: "fuel"; record: DriverFuelRecord }
  | { kind: "expense"; record: DriverExpenseRecord }
  | { kind: "advance"; record: DriverAdvanceRecord };

interface JournalCache {
  items: JournalItem[];
  total: number;
}

interface RecordsViewProps {
  refreshToken?: number;
  tripId?: string;
}

const numberFormat = new Intl.NumberFormat("pt-MZ", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateFormat = new Intl.DateTimeFormat("pt-MZ", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function timestamp(item: JournalItem): string {
  if (item.kind === "checklist") return item.record.completed_at ?? item.record.started_at;
  if (item.kind === "fuel") return item.record.fuel_date;
  if (item.kind === "expense") return item.record.incurred_at;
  return item.record.issued_at;
}

function checklistTitle(value: string): string {
  if (value === "pre_trip") return "Checklist antes da viagem";
  if (value === "post_trip") return "Checklist após a viagem";
  return "Checklist operacional";
}

function expenseTitle(record: DriverExpenseRecord): string {
  if (record.entry_type === "adjustment") return "Ajuste de despesa";
  if (record.entry_type === "reversal") return "Estorno de despesa";
  const labels: Record<string, string> = {
    toll: "Portagem",
    meal: "Alimentação",
    lodging: "Alojamento",
    parking: "Estacionamento",
    repair: "Reparação",
    other: "Outra despesa",
  };
  return labels[record.expense_type] ?? "Despesa de viagem";
}

function money(value: string, currency: string): string {
  return `${numberFormat.format(Number(value))} ${currency}`;
}

function RecordCard({ item }: { item: JournalItem }) {
  const when = dateFormat.format(new Date(timestamp(item)));
  if (item.kind === "checklist") {
    return (
      <article className="record-card">
        <CheckCircle2 aria-hidden="true" />
        <div><strong>{checklistTitle(item.record.checklist_type)}</strong><span>Concluído · {when}</span></div>
      </article>
    );
  }
  if (item.kind === "fuel") {
    return (
      <article className="record-card">
        <Fuel aria-hidden="true" />
        <div>
          <strong>Abastecimento</strong>
          <span>{numberFormat.format(Number(item.record.liters))} L</span>
          <small>{money(item.record.total_cost, "MZN")} · {item.record.station_name || "Posto não indicado"} · {when}</small>
        </div>
      </article>
    );
  }
  if (item.kind === "expense") {
    return (
      <article className="record-card">
        <ReceiptText aria-hidden="true" />
        <div>
          <strong>{expenseTitle(item.record)}</strong>
          <span>{money(item.record.amount, item.record.currency)}</span>
          <small>{item.record.correction_reason ? `${item.record.correction_reason} · ` : ""}{when}</small>
        </div>
      </article>
    );
  }
  return (
    <article className="record-card">
      <WalletCards aria-hidden="true" />
      <div><strong>Despacho de viagem</strong><span>{money(item.record.total_amount, item.record.currency)} · Emitido</span><small>{when}</small></div>
    </article>
  );
}

export function RecordsView({ refreshToken = 0, tripId }: RecordsViewProps) {
  const [items, setItems] = useState<JournalItem[]>([]);
  const [filter, setFilter] = useState<"all" | RecordKind>("all");
  const [state, setState] = useState<"loading" | "ready" | "error" | "forbidden">("loading");
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  const load = useCallback(async () => {
    const scope = getCurrentIdentityScope();
    const cacheKey = `records:all:${tripId ?? "all"}:0`;
    setState("loading");
    setCachedAt(null);
    try {
      const [checklists, fuel, expenses, advances] = await Promise.all([
        listDriverChecklistRecords(20, 0, tripId),
        listDriverFuelRecords(20, 0, tripId),
        listDriverExpenseRecords(20, 0, tripId),
        listDriverAdvanceRecords(20, 0, tripId),
      ]);
      const nextItems: JournalItem[] = [
        ...checklists.items.map((record) => ({ kind: "checklist" as const, record })),
        ...fuel.items.map((record) => ({ kind: "fuel" as const, record })),
        ...expenses.items.map((record) => ({ kind: "expense" as const, record })),
        ...advances.items.map((record) => ({ kind: "advance" as const, record })),
      ].sort((left, right) => Date.parse(timestamp(right)) - Date.parse(timestamp(left)));
      const data = { items: nextItems, total: nextItems.length };
      setItems(nextItems);
      setState("ready");
      if (scope) await saveDriverReadCache(scope, cacheKey, data);
    } catch (error) {
      const cached = scope
        ? await getDriverReadCache<JournalCache>(scope, cacheKey)
        : undefined;
      if (cached) {
        setItems(cached.data.items);
        setCachedAt(cached.cachedAt);
        setState("ready");
      } else {
        setItems([]);
        setState(error instanceof HttpContractError && error.status === 403 ? "forbidden" : "error");
      }
    }
  }, [tripId]);

  useEffect(() => { void load(); }, [load, refreshToken, retryToken]);

  const visibleItems = filter === "all"
    ? items
    : items.filter((item) => item.kind === filter);

  return (
    <section className="records-workspace" aria-labelledby="records-title">
      <div className="workspace-heading">
        <span>Diário operacional</span>
        <h2 id="records-title">Registos</h2>
        <p>Histórico imutável de checklist, combustível, despesas e despachos.</p>
      </div>

      <div className="record-filters" aria-label="Filtrar registos">
        {([
          ["all", "Todos"],
          ["checklist", "Checklist"],
          ["fuel", "Combustível"],
          ["expense", "Despesas"],
          ["advance", "Despachos"],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={filter === value ? "selected" : ""}
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {cachedAt && (
        <div className="records-degraded" role="status">
          <AlertTriangle aria-hidden="true" />
          <span>Sem ligação — dados guardados em {dateFormat.format(new Date(cachedAt))}, somente leitura.</span>
        </div>
      )}

      {state === "loading" && <div className="records-state" role="status">A carregar registos…</div>}
      {state === "forbidden" && <div className="records-state records-state--error" role="alert">Sem permissão para consultar registos</div>}
      {state === "error" && (
        <div className="records-state records-state--error" role="alert">
          <strong>Não foi possível carregar os registos</strong>
          <button type="button" onClick={() => setRetryToken((value) => value + 1)}>Tentar novamente</button>
        </div>
      )}
      {state === "ready" && visibleItems.length === 0 && (
        <div className="records-state"><strong>Ainda não há registos</strong><span>Os registos operacionais aparecerão aqui.</span></div>
      )}
      {state === "ready" && visibleItems.length > 0 && (
        <div className="records-list" aria-label="Registos operacionais">
          {visibleItems.map((item) => <RecordCard key={`${item.kind}:${item.record.id}`} item={item} />)}
        </div>
      )}
    </section>
  );
}
