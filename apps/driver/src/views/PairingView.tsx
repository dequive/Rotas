import { Smartphone, Truck } from "lucide-react";
import { useState } from "react";
import { pairDevice, type AuthState } from "../api";

function generateDeviceId(): string {
  const existing = localStorage.getItem("rotas_device_id");
  if (existing) return existing;
  const id = `device_${crypto.randomUUID()}`;
  localStorage.setItem("rotas_device_id", id);
  return id;
}

export function PairingView({ onPaired }: { onPaired: (auth: AuthState) => void }) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (code.trim().length < 4) return;
    setError(null);
    setLoading(true);
    try {
      const deviceId = generateDeviceId();
      const auth = await pairDevice(code.trim().toUpperCase(), deviceId);
      onPaired(auth);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Código inválido ou expirado.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="pairing-shell">
      <div className="pairing-card">
        <div className="pairing-brand">
          <Truck size={36} />
          <span>ROTAS</span>
        </div>
        <p className="pairing-subtitle">App do motorista</p>

        <div className="pairing-instructions">
          <Smartphone size={20} />
          <p>Peça ao seu gestor o código de pareamento de 6 caracteres e introduza-o abaixo.</p>
        </div>

        <form onSubmit={handleSubmit} className="pairing-form">
          <input
            className="pairing-input"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="ABC123"
            maxLength={8}
            required
            autoComplete="off"
            autoCapitalize="characters"
          />
          {error && <p className="pairing-error">{error}</p>}
          <button type="submit" className="pairing-btn" disabled={loading || code.trim().length < 4}>
            {loading ? "A parear..." : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
