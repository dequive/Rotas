"use client";

import { useReportWebVitals } from "next/web-vitals";
import { recordManagerWebVital } from "@/app/lib/ux-telemetry";

export function WebVitalsReporter() {
  useReportWebVitals((vital) => {
    void recordManagerWebVital(vital);
  });

  return null;
}
