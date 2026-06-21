"use client";

import { useState } from "react";

type JobState = "idle" | "pending" | "done" | "failed";

interface JobStatus {
  job_id: string;
  status: string;
}

interface ExportButtonsProps {
  currentMonth: string; // YYYY-MM format
}

export default function ExportButtons({ currentMonth }: ExportButtonsProps) {
  const [fuelState, setFuelState] = useState<JobState>("idle");
  const [complianceState, setComplianceState] = useState<JobState>("idle");

  async function triggerFuelReport() {
    setFuelState("pending");
    try {
      const res = await fetch(
        `/api/analytics/fuel-report?month=${encodeURIComponent(currentMonth)}`,
      );
      const data: JobStatus = await res.json();
      if (!data.job_id) {
        setFuelState("failed");
        return;
      }
      // Poll every 3 seconds for up to 60 seconds (20 attempts)
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (attempts > 20) {
          clearInterval(interval);
          setFuelState("failed");
          return;
        }
        try {
          const poll = await fetch(
            `/api/analytics/fuel-report?month=${encodeURIComponent(currentMonth)}`,
          );
          const pollData: JobStatus = await poll.json();
          if (pollData.status === "done") {
            clearInterval(interval);
            setFuelState("done");
          } else if (pollData.status === "failed") {
            clearInterval(interval);
            setFuelState("failed");
          }
        } catch {
          // continue polling
        }
      }, 3000);
    } catch {
      setFuelState("failed");
    }
  }

  async function triggerComplianceReport() {
    setComplianceState("pending");
    try {
      const res = await fetch("/api/analytics/compliance-report");
      const data: JobStatus = await res.json();
      if (!data.job_id) {
        setComplianceState("failed");
        return;
      }
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (attempts > 20) {
          clearInterval(interval);
          setComplianceState("failed");
          return;
        }
        try {
          const poll = await fetch("/api/analytics/compliance-report");
          const pollData: JobStatus = await poll.json();
          if (pollData.status === "done") {
            clearInterval(interval);
            setComplianceState("done");
          } else if (pollData.status === "failed") {
            clearInterval(interval);
            setComplianceState("failed");
          }
        } catch {
          // continue polling
        }
      }, 3000);
    } catch {
      setComplianceState("failed");
    }
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Fuel Export */}
      <button
        onClick={triggerFuelReport}
        disabled={fuelState === "pending"}
        className="flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-md
          bg-panel border border-line text-ink hover:bg-surface-2 disabled:opacity-60
          disabled:cursor-not-allowed transition-colors"
      >
        {fuelState === "pending" ? (
          <>
            <span
              className="inline-block w-3 h-3 border-2 border-amber border-t-transparent rounded-full animate-spin"
            />
            A gerar XLSX...
          </>
        ) : fuelState === "done" ? (
          <span className="text-green-600">XLSX pronto — ver em Ficheiros</span>
        ) : fuelState === "failed" ? (
          <span className="text-red-600">Erro — tente novamente</span>
        ) : (
          "Exportar Combustível (XLSX)"
        )}
      </button>

      {/* Compliance Export */}
      <button
        onClick={triggerComplianceReport}
        disabled={complianceState === "pending"}
        className="flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-md
          bg-panel border border-line text-ink hover:bg-surface-2 disabled:opacity-60
          disabled:cursor-not-allowed transition-colors"
      >
        {complianceState === "pending" ? (
          <>
            <span
              className="inline-block w-3 h-3 border-2 border-amber border-t-transparent rounded-full animate-spin"
            />
            A gerar PDF...
          </>
        ) : complianceState === "done" ? (
          <span className="text-green-600">PDF pronto — ver em Ficheiros</span>
        ) : complianceState === "failed" ? (
          <span className="text-red-600">Erro — tente novamente</span>
        ) : (
          "Exportar Conformidade (PDF)"
        )}
      </button>
    </div>
  );
}
