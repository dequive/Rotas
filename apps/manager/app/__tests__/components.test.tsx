import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { Button } from "@/components/ui/button";

describe("Manager Standard Components", () => {
  describe("KpiCard", () => {
    it("renders label, value, and trend", () => {
      render(
        <KpiCard
          label="Total Trips"
          value="142"
          trend={{ direction: "up", label: "12% vs last month" }}
        />
      );
      expect(screen.getByText(/total trips/i)).toBeInTheDocument();
      expect(screen.getByText("142")).toBeInTheDocument();
      expect(screen.getByText("12% vs last month")).toBeInTheDocument();
      expect(screen.getByText("↑")).toBeInTheDocument();
    });

    it("renders loading skeleton state", () => {
      const { container } = render(
        <KpiCard label="Total Trips" value="142" loading={true} />
      );
      expect(
        container.querySelector('[class~="motion-safe:animate-pulse"]')
      ).toBeInTheDocument();
    });
  });

  describe("StatusBadge", () => {
    it("renders status with label and dot", () => {
      render(<StatusBadge status="em-rota" />);
      expect(screen.getByText("Em Rota")).toBeInTheDocument();
    });

    it("supports override label", () => {
      render(<StatusBadge status="concluida" label="Done" />);
      expect(screen.getByText("Done")).toBeInTheDocument();
    });
  });

  describe("Button", () => {
    it("renders children text", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
    });

    it("supports disabled state", () => {
      render(<Button disabled>Disabled Button</Button>);
      expect(screen.getByRole("button", { name: "Disabled Button" })).toBeDisabled();
    });
  });
});
