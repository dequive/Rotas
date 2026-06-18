export function demoFallbackAllowed(): boolean {
  if (process.env.ROTAS_ALLOW_DEMO_FALLBACK === "1") {
    return true;
  }
  if (process.env.ROTAS_DISABLE_DEMO_FALLBACK === "1") {
    return false;
  }
  if (process.env.VERCEL_ENV === "production") {
    return false;
  }
  return process.env.NODE_ENV !== "production";
}

export function throwWhenDemoFallbackDisabled(area: string, error: unknown): void {
  if (demoFallbackAllowed()) {
    return;
  }
  const detail = error instanceof Error ? error.message : "API unavailable.";
  throw new Error(`${area}: production data unavailable. ${detail}`);
}
