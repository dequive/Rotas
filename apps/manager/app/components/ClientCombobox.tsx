"use client";

import { useState, useEffect, useRef } from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Client {
  id: string;
  trading_name: string;
  nuit: string;
}

interface ClientComboboxProps {
  value?: string;
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
            className={cn(
              "w-full min-h-[38px] flex items-center justify-between px-2.5 text-[13px]",
              "border border-border-strong rounded-md bg-surface transition-colors duration-100",
              "focus:outline-none focus:border-amber focus:ring-2 focus:ring-amber/20",
              selectedClient ? "text-ink" : "text-placeholder",
              disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <span>{selectedClient ? selectedClient.trading_name : "Pesquisar cliente…"}</span>
            <ChevronsUpDown size={14} className="opacity-50 flex-shrink-0 ml-2" />
          </button>
        </PopoverTrigger>

        <PopoverContent className="w-80 p-0" align="start" sideOffset={4}>
          <div className="flex items-center gap-2 px-2.5 py-2 border-b border-border">
            <Search size={13} className="text-muted flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Pesquisar cliente…"
              className="flex-1 border-none outline-none bg-transparent text-[13px] text-ink"
            />
          </div>

          <div className="max-h-60 overflow-y-auto">
            {error && <p className="p-3 text-xs text-error">{error}</p>}

            {loading && !error && (
              <div className="p-2 flex flex-col gap-1">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            )}

            {!loading && !error && filtered.length === 0 && (
              <p className="p-3 text-xs text-muted text-center">
                Nenhum cliente encontrado. Crie um cliente primeiro.
              </p>
            )}

            {!loading && !error && filtered.length > 0 && (
              <ul role="listbox" className="list-none m-0 py-1">
                {filtered.map((client) => (
                  <li
                    key={client.id}
                    role="option"
                    aria-selected={value === client.id}
                    onClick={() => {
                      onChange(client.id, client.trading_name);
                      setOpen(false);
                    }}
                    className={cn(
                      "flex items-center gap-2 px-2.5 py-2 cursor-pointer hover:bg-surface-2 transition-colors duration-75",
                      value === client.id ? "bg-surface-2" : "",
                    )}
                  >
                    <Check
                      size={13}
                      className={cn(
                        "flex-shrink-0 text-amber",
                        value === client.id ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <span className="flex-1 text-[13px] text-ink">{client.trading_name}</span>
                    <span className="text-[11px] font-mono text-muted flex-shrink-0">
                      {client.nuit}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </PopoverContent>
      </Popover>

      {selectedClient && (
        <p className="text-[11px] font-mono text-muted m-0">NUIT: {selectedClient.nuit}</p>
      )}
    </div>
  );
}
