"use client";

import { useState, useEffect, useRef } from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";

interface Client {
  id: string;
  trading_name: string;
  nuit: string;
}

interface ClientComboboxProps {
  value?: string;              // selected client_id UUID
  onChange: (clientId: string, tradingName: string) => void;
  disabled?: boolean;
}

export function ClientCombobox({ value, onChange, disabled }: ClientComboboxProps) {
  const [open, setOpen] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedClient = clients.find((c) => c.id === value);

  // Fetch clients when popover opens. Fetches from the Next.js API proxy route
  // (/api/clients) which reads httpOnly cookies server-side and forwards to backend.
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    fetch("/api/clients?limit=200", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error("Erro ao carregar clientes");
        return r.json() as Promise<Client[]>;
      })
      .then((data) => {
        setClients(Array.isArray(data) ? data : []);
      })
      .catch(() => setError("Erro ao carregar clientes"))
      .finally(() => setLoading(false));
  }, [open]);

  // Focus search input when popover opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [open]);

  const filtered = query.trim()
    ? clients.filter(
        (c) =>
          c.trading_name.toLowerCase().includes(query.toLowerCase()) ||
          c.nuit.includes(query)
      )
    : clients;

  return (
    <div className="flex flex-col gap-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            role="combobox"
            aria-expanded={open}
            aria-haspopup="listbox"
            disabled={disabled}
            style={{
              width: "100%",
              minHeight: "38px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 10px",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--r-md, 6px)",
              background: "var(--surface)",
              color: selectedClient ? "var(--ink)" : "var(--placeholder)",
              fontSize: "13px",
              fontFamily: "Manrope, sans-serif",
              cursor: disabled ? "not-allowed" : "pointer",
              opacity: disabled ? 0.6 : 1,
              transition: "border-color 80ms ease-out",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--amber)";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(245,158,11,.12)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border-strong)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <span>{selectedClient ? selectedClient.trading_name : "Pesquisar cliente…"}</span>
            <ChevronsUpDown size={14} style={{ opacity: 0.5, flexShrink: 0, marginLeft: 8 }} />
          </button>
        </PopoverTrigger>

        <PopoverContent
          className="p-0"
          style={{ width: "320px" }}
          align="start"
          sideOffset={4}
        >
          {/* Search input */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 10px",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <Search size={13} style={{ color: "var(--muted)", flexShrink: 0 }} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Pesquisar cliente…"
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontSize: "13px",
                fontFamily: "Manrope, sans-serif",
                color: "var(--ink)",
              }}
            />
          </div>

          {/* List area */}
          <div style={{ maxHeight: "240px", overflowY: "auto" }}>
            {error && (
              <p style={{ padding: "12px", fontSize: "12px", color: "var(--error)" }}>{error}</p>
            )}

            {loading && !error && (
              <div style={{ padding: "8px" }}>
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-8 w-full mb-1" />
                ))}
              </div>
            )}

            {!loading && !error && filtered.length === 0 && (
              <p
                style={{
                  padding: "12px",
                  fontSize: "12px",
                  color: "var(--muted)",
                  textAlign: "center",
                }}
              >
                Nenhum cliente encontrado. Crie um cliente primeiro.
              </p>
            )}

            {!loading && !error && filtered.length > 0 && (
              <ul role="listbox" style={{ listStyle: "none", margin: 0, padding: "4px 0" }}>
                {filtered.map((client) => (
                  <li
                    key={client.id}
                    role="option"
                    aria-selected={value === client.id}
                    onClick={() => {
                      onChange(client.id, client.trading_name);
                      setOpen(false);
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 10px",
                      cursor: "pointer",
                      background: value === client.id ? "var(--surface-2)" : "transparent",
                      transition: "background 80ms ease-out",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--surface-2)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background =
                        value === client.id ? "var(--surface-2)" : "transparent";
                    }}
                  >
                    <Check
                      size={13}
                      style={{
                        flexShrink: 0,
                        color: "var(--amber)",
                        opacity: value === client.id ? 1 : 0,
                      }}
                    />
                    <span style={{ flex: 1, fontSize: "13px", color: "var(--ink)" }}>
                      {client.trading_name}
                    </span>
                    <span
                      style={{
                        fontSize: "11px",
                        fontFamily: "IBM Plex Mono, monospace",
                        color: "var(--muted)",
                        flexShrink: 0,
                      }}
                    >
                      {client.nuit}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </PopoverContent>
      </Popover>

      {/* NUIT confirmation below trigger when a client is selected */}
      {selectedClient && (
        <p
          style={{
            fontSize: "11px",
            fontFamily: "IBM Plex Mono, monospace",
            color: "var(--muted)",
            margin: 0,
          }}
        >
          NUIT: {selectedClient.nuit}
        </p>
      )}
    </div>
  );
}
