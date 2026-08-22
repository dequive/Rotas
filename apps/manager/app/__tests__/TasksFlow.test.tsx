import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  bffFetch: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: state.push, refresh: state.refresh }),
}));

vi.mock("../lib/bff", () => ({
  bffFetch: state.bffFetch,
  bffRequest: vi.fn(),
}));

vi.mock("../components/SidebarLayout", () => ({
  SidebarLayout: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import NovaTarefaPage from "../tarefas/nova/page";
import { TaskActions } from "../tarefas/components/TaskActions";
import { TaskNotes } from "../tarefas/components/TaskNotes";

describe("Central de Tarefas flows", () => {
  beforeEach(() => {
    state.bffFetch.mockReset();
    state.push.mockReset();
    state.refresh.mockReset();
  });

  it("loads real vehicles and case types and creates a canonical Governance case", async () => {
    state.bffFetch.mockImplementation((target: string) => {
      if (target === "/api/vehicles?limit=200") {
        return Promise.resolve([{ id: "vehicle-1", plate: "ABC-12-34" }]);
      }
      if (target === "/api/governance/case-types") {
        return Promise.resolve([
          { code: "rotas.incident", name: "Incidente Operacional" },
        ]);
      }
      if (target === "/api/governance/cases") {
        return Promise.resolve({ id: "case-1" });
      }
      throw new Error(`Unexpected target: ${target}`);
    });

    render(<NovaTarefaPage />);
    fireEvent.click(screen.getByRole("button", { name: /Governance/i }));
    await screen.findByRole("option", { name: "Incidente Operacional" });
    fireEvent.change(screen.getByLabelText(/Tipo de caso/i), {
      target: { value: "rotas.incident" },
    });
    fireEvent.change(screen.getByLabelText(/Título resumido/i), {
      target: { value: "Falha de rede" },
    });
    fireEvent.change(screen.getByLabelText(/Descrição detalhada/i), {
      target: { value: "Sem acesso desde as 10h" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar Tarefa" }));

    await waitFor(() =>
      expect(state.bffFetch).toHaveBeenCalledWith(
        "/api/governance/cases",
        expect.objectContaining({
          path: "/api/governance/cases",
          method: "POST",
          body: JSON.stringify({
            case_type_code: "rotas.incident",
            payload: {
              title: "Falha de rede",
              description: "Sem acesso desde as 10h",
            },
          }),
        }),
      ),
    );
    expect(state.push).toHaveBeenCalledWith("/tarefas");
  });

  it("does not report success when a Governance transition fails", async () => {
    state.bffFetch.mockRejectedValue(new Error("illegal transition"));
    render(
      <TaskActions
        taskId="22222222-2222-4222-8222-222222222222"
        source="governance"
        currentStatus="open"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Resolver caso/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível atualizar o caso",
    );
    expect(state.refresh).not.toHaveBeenCalled();
  });

  it("does not render a fake Governance notes form when the contract does not exist", () => {
    render(
      <TaskNotes
        taskId="22222222-2222-4222-8222-222222222222"
        source="governance"
      />,
    );

    expect(screen.queryByPlaceholderText(/Adicionar um comentário/i)).toBeNull();
    expect(screen.getByText(/Notas ainda não estão disponíveis/i)).toBeVisible();
  });

  it("shows an inline error when a Workshop note cannot be persisted", async () => {
    state.bffFetch.mockRejectedValue(new Error("upstream unavailable"));
    render(
      <TaskNotes
        taskId="22222222-2222-4222-8222-222222222222"
        source="workshop"
      />,
    );

    fireEvent.change(screen.getByLabelText(/Nova nota/i), {
      target: { value: "Inspeção concluída" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Enviar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível adicionar a nota",
    );
    expect(state.refresh).not.toHaveBeenCalled();
  });
});
