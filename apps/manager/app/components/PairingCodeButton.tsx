"use client";

import { Copy, Smartphone } from "lucide-react";
import { useState } from "react";
import { Button } from "@/app/components/ui/Button";
import { IconButton } from "@/app/components/ui/IconButton";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

export function PairingCodeButton({ driverId, driverName }: { driverId: string; driverName: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/drivers/pairing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ driver_id: driverId }),
      });
      const body = (await res.json()) as { pairing_code?: string; expires_at?: string; detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao gerar código."); return; }
      setCode(body.pairing_code ?? null);
      setExpiresAt(body.expires_at ?? null);
    } finally {
      setLoading(false);
    }
  }

  function copyCode() {
    if (!code) return;
    void navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleOpen() {
    setOpen(true);
    setCode(null);
    setExpiresAt(null);
    setError(null);
    void generate();
  }

  return (
    <>
      <IconButton label="Gerar código de pareamento" onClick={handleOpen}>
        <Smartphone size={15} />
      </IconButton>

      <ModalDialog
        open={open}
        onClose={() => setOpen(false)}
        title={`Código de pareamento — ${driverName}`}
        className="pairing-modal"
      >
        <div className="pairing-body">
          {loading && <p className="muted">A gerar código...</p>}
          {error && <p className="form-error">{error}</p>}
          {code && (
            <>
              <p className="muted">Código válido por 15 minutos. O motorista deve introduzir este código na app.</p>
              <div className="pairing-code">
                <span>{code}</span>
                <IconButton onClick={copyCode} label="Copiar código">
                  <Copy size={16} />
                </IconButton>
              </div>
              {copied && <p className="success-msg">Copiado!</p>}
              {expiresAt && (
                <p className="muted">Expira às {new Date(expiresAt).toLocaleTimeString("pt-MZ")}</p>
              )}
              <Button variant="secondary" onClick={() => void generate()}>Novo código</Button>
            </>
          )}
        </div>
      </ModalDialog>
    </>
  );
}
