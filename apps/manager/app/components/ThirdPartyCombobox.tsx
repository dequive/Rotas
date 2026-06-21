"use client";

import { useState, useEffect, useRef } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThirdPartyOption {
  id: string;
  name: string;
  tax_id: string | null;
}

interface ThirdPartyComboboxProps {
  roleType: "supplier" | "service_provider" | "client";
  value: string | null;
  displayValue: string | null;
  onChange: (selected: { id: string; name: string } | null) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
}

export function ThirdPartyCombobox({
  roleType,
  value,
  displayValue,
  onChange,
  placeholder = "Pesquisar...",
  label,
  disabled = false,
}: ThirdPartyComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<ThirdPartyOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    const qs = new URLSearchParams({ role_type: roleType, limit: "100" });
    if (search.trim()) qs.set("name", search.trim());
    fetch(`/api/third-party?${qs}`, { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error("Erro ao carregar terceiros");
        return r.json();
      })
      .then((data) => {
        const items = Array.isArray(data) ? data : (data.items ?? []);
        setOptions(items);
      })
      .catch(() => {
        setError("Erro ao carregar lista");
        setOptions([]);
      })
      .finally(() => setLoading(false));
  }, [open, search, roleType]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setSearch("");
    }
  }, [open]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selectedOption = options.find((o) => o.id === value);
  const displayText = selectedOption?.name ?? (value ? displayValue : displayValue) ?? "";

  function handleSelect(opt: ThirdPartyOption) {
    onChange({ id: opt.id, name: opt.name });
    setOpen(false);
    setSearch("");
  }

  function handleClear(e: React.MouseEvent) {
    e.stopPropagation();
    onChange(null);
  }

  return (
    <div className="relative" ref={ref}>
      {label && (
        <label className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">
          {label}
        </label>
      )}

      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        className={cn(
          "w-full min-h-[38px] flex items-center justify-between gap-2 px-2.5 text-left text-[13px]",
          "border border-border-strong rounded-md bg-surface transition-colors duration-100",
          "focus:outline-none focus:border-amber focus:ring-2 focus:ring-amber/20",
          displayText ? "text-ink" : "text-placeholder",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
          {displayText || placeholder}
        </span>
        <span className="flex items-center gap-1 flex-shrink-0">
          {value && (
            <span
              onClick={handleClear}
              className="text-muted cursor-pointer flex"
              title="Limpar selecção"
            >
              <X size={12} />
            </span>
          )}
          <ChevronDown size={14} className="text-muted" />
        </span>
      </button>

      {open && (
        <div className="absolute z-50 top-full mt-1 w-full min-w-60 bg-surface border border-border rounded-md shadow-lg max-h-[280px] flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-2.5 py-2 border-b border-border">
            <Search size={13} className="text-muted flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Pesquisar nome..."
              className="flex-1 border-none outline-none bg-transparent text-[13px] text-ink"
            />
          </div>

          <div className="overflow-y-auto flex-1">
            {error && <p className="p-3 text-xs text-error">{error}</p>}

            {loading && !error && (
              <p className="p-3 text-xs text-muted">A carregar...</p>
            )}

            {!loading && !error && options.length === 0 && (
              <p className="p-3 text-xs text-muted text-center">Nenhum resultado</p>
            )}

            {!loading && !error && options.length > 0 && (
              <ul role="listbox" className="list-none m-0 py-1">
                {options.map((opt) => (
                  <li
                    key={opt.id}
                    role="option"
                    aria-selected={opt.id === value}
                    onClick={() => handleSelect(opt)}
                    className={cn(
                      "flex items-center gap-2 px-2.5 py-2 cursor-pointer hover:bg-surface-2 transition-colors duration-75",
                      opt.id === value ? "bg-amber/10" : "",
                    )}
                  >
                    <Check
                      size={13}
                      className={cn(
                        "flex-shrink-0 text-amber",
                        opt.id === value ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <span className="flex-1 text-[13px] text-ink">{opt.name}</span>
                    {opt.tax_id && (
                      <span className="text-[11px] font-mono text-muted flex-shrink-0">
                        {opt.tax_id}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
