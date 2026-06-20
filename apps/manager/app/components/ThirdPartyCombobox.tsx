"use client";

import { useState, useEffect, useRef } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";

interface ThirdPartyOption {
  id: string;
  name: string;
  tax_id: string | null;
}

interface ThirdPartyComboboxProps {
  roleType: "supplier" | "service_provider" | "client";
  value: string | null; // currently selected third_party_id
  displayValue: string | null; // free-text snapshot to show when no id selected
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

  // Fetch options from the Next.js proxy route (avoids httpOnly cookie issue)
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
        // Backend returns array or { items: [] }
        const items = Array.isArray(data) ? data : (data.items ?? []);
        setOptions(items);
      })
      .catch(() => {
        setError("Erro ao carregar lista");
        setOptions([]);
      })
      .finally(() => setLoading(false));
  }, [open, search, roleType]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setSearch("");
    }
  }, [open]);

  // Close dropdown on outside click
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
        <label
          style={{
            display: "block",
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "var(--muted)",
            marginBottom: "4px",
            fontFamily: "Manrope, sans-serif",
          }}
        >
          {label}
        </label>
      )}

      {/* Trigger button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
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
          color: displayText ? "var(--ink)" : "var(--placeholder)",
          fontSize: "13px",
          fontFamily: "Manrope, sans-serif",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          transition: "border-color 80ms ease-out",
          gap: 8,
          textAlign: "left",
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
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {displayText || placeholder}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
          {value && (
            <span
              onClick={handleClear}
              style={{ color: "var(--muted)", cursor: "pointer", display: "flex" }}
              title="Limpar selecção"
            >
              <X size={12} />
            </span>
          )}
          <ChevronDown size={14} style={{ color: "var(--muted)" }} />
        </span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          style={{
            position: "absolute",
            zIndex: 50,
            top: "100%",
            marginTop: 4,
            width: "100%",
            minWidth: 240,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-md, 6px)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            maxHeight: 280,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
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
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Pesquisar nome..."
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

          {/* Options list */}
          <div style={{ overflowY: "auto", flex: 1 }}>
            {error && (
              <p style={{ padding: "12px", fontSize: "12px", color: "var(--error)" }}>{error}</p>
            )}

            {loading && !error && (
              <p style={{ padding: "12px", fontSize: "12px", color: "var(--muted)" }}>
                A carregar...
              </p>
            )}

            {!loading && !error && options.length === 0 && (
              <p
                style={{
                  padding: "12px",
                  fontSize: "12px",
                  color: "var(--muted)",
                  textAlign: "center",
                }}
              >
                Nenhum resultado
              </p>
            )}

            {!loading && !error && options.length > 0 && (
              <ul role="listbox" style={{ listStyle: "none", margin: 0, padding: "4px 0" }}>
                {options.map((opt) => (
                  <li
                    key={opt.id}
                    role="option"
                    aria-selected={opt.id === value}
                    onClick={() => handleSelect(opt)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 10px",
                      cursor: "pointer",
                      background: opt.id === value ? "rgba(245,158,11,0.08)" : "transparent",
                      transition: "background 80ms ease-out",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--surface-2)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background =
                        opt.id === value ? "rgba(245,158,11,0.08)" : "transparent";
                    }}
                  >
                    <Check
                      size={13}
                      style={{
                        flexShrink: 0,
                        color: "var(--amber)",
                        opacity: opt.id === value ? 1 : 0,
                      }}
                    />
                    <span
                      style={{
                        flex: 1,
                        fontSize: "13px",
                        color: "var(--ink)",
                        fontFamily: "Manrope, sans-serif",
                      }}
                    >
                      {opt.name}
                    </span>
                    {opt.tax_id && (
                      <span
                        style={{
                          fontSize: "11px",
                          fontFamily: "IBM Plex Mono, monospace",
                          color: "var(--muted)",
                          flexShrink: 0,
                        }}
                      >
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
