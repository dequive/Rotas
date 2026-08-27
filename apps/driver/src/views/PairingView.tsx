import { RefreshCw, ShieldCheck, Smartphone, Truck } from "lucide-react";
import { useState } from "react";
import { pairDevice, type AuthState } from "../api";

function generateDeviceId(): string {
  const existing = localStorage.getItem("rotas_device_id");
  if (existing) return existing;
  const id = `device_${crypto.randomUUID()}`;
  localStorage.setItem("rotas_device_id", id);
  return id;
}

export function PairingView({
  onPaired,
  onUpdate,
}: {
  onPaired: (auth: AuthState) => void;
  onUpdate?: () => void;
}) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (code.length !== 6) return;
    setError(null);
    setLoading(true);
    try {
      const deviceId = generateDeviceId();
      const auth = await pairDevice(code, deviceId);
      onPaired(auth);
    } catch {
      setError(
        navigator.onLine
          ? "Não foi possível emparelhar. Confirme o código ou peça um novo ao gestor."
          : "Sem ligação à internet. Ligue-se à rede e tente novamente.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="pairing-shell">
      <section className="pairing-card" aria-labelledby="pairing-title">
        <header className="pairing-brand">
          <span className="pairing-brand__mark" aria-hidden="true">
            <Truck size={24} />
          </span>
          <span>
            <strong>ROTAS</strong>
            <small>Aplicação do motorista</small>
          </span>
        </header>

        <div className="pairing-heading">
          <span>ATIVAÇÃO SEGURA</span>
          <h1 id="pairing-title">Emparelhe este telefone</h1>
          <p>Associe o dispositivo à sua conta de motorista para receber viagens e documentos.</p>
        </div>

        <div className="pairing-instructions">
          <Smartphone size={20} />
          <p>
            <strong>Use o código de 6 dígitos</strong>
            <span>Peça ao gestor para gerar um código novo. É válido durante 15 minutos.</span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="pairing-form">
          <label htmlFor="pairing-code" className="pairing-label">
            Código de emparelhamento
          </label>
          <input
            id="pairing-code"
            className="pairing-input"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="000000"
            maxLength={6}
            required
            inputMode="numeric"
            pattern="[0-9]{6}"
            autoComplete="one-time-code"
            aria-describedby={error ? "pairing-help pairing-error" : "pairing-help"}
            aria-invalid={error ? "true" : "false"}
          />
          <span id="pairing-help" className="pairing-help">
            Introduza os seis números apresentados pelo gestor.
          </span>
          {error && (
            <p id="pairing-error" role="alert" className="pairing-error">
              {error}
            </p>
          )}
          <button type="submit" className="pairing-btn" disabled={loading || code.length !== 6}>
            {loading ? "A emparelhar…" : "Emparelhar dispositivo"}
          </button>
        </form>

        {onUpdate && (
          <aside className="pairing-update" role="status" aria-live="polite">
            <span>
              <strong>Nova versão pronta</strong>
              <small>Atualize antes de emparelhar este telefone.</small>
            </span>
            <button type="button" onClick={onUpdate}>
              <RefreshCw size={16} aria-hidden="true" />
              Atualizar aplicação
            </button>
          </aside>
        )}

        <footer className="pairing-security">
          <ShieldCheck size={18} aria-hidden="true" />
          <span>O código é de uso único. Este telefone ficará associado apenas à sua conta.</span>
        </footer>
      </section>
    </main>
  );
}
