"use client";

import { bffFetch } from "./bff";
import type { DriverHub360Response, ScorecardData } from "./drivers-api";

export async function loadDriverScorecard(
  driverId: string,
  days = 30,
): Promise<ScorecardData | null> {
  try {
    return await bffFetch<ScorecardData>(
      `/api/v1/drivers/${driverId}/scorecard?days=${days}`,
    );
  } catch {
    return null;
  }
}

export function loadDriverHub360(id: string): Promise<DriverHub360Response> {
  return bffFetch<DriverHub360Response>(`/api/v1/drivers/${id}/hub360`);
}
