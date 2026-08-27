import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  inviteUser: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: state.refresh }),
}));

vi.mock("../settings/actions", () => ({
  updateUserProfile: vi.fn(),
  inviteUser: state.inviteUser,
  changeUserRole: vi.fn(),
  updateTenantSettings: vi.fn(),
}));

import { SettingsClient } from "../settings/SettingsClient";

describe("SettingsClient access management", () => {
  beforeEach(() => {
    state.inviteUser.mockReset();
    state.refresh.mockReset();
    state.inviteUser.mockResolvedValue({ ok: true });
  });

  it("creates a user with the temporary password required by the backend", async () => {
    render(
      <SettingsClient
        userId="owner-1"
        userRole="owner"
        initialName="Owner"
        initialEmail="owner@rotas.local"
        initialPhone=""
        limits={null}
        users={[]}
        tenant={null}
        drivers={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Gestão de Acessos" }));
    fireEvent.change(screen.getByPlaceholderText("Nome completo"), {
      target: { value: "Gestor Comercial" },
    });
    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "gestor@rotas.local" },
    });
    fireEvent.change(screen.getByLabelText("Palavra-passe temporária"), {
      target: { value: "TempPass-2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar utilizador" }));

    await waitFor(() => {
      expect(state.inviteUser).toHaveBeenCalledWith({
        email: "gestor@rotas.local",
        full_name: "Gestor Comercial",
        password: "TempPass-2026",
        role: "viewer",
      });
    });
  });
});
