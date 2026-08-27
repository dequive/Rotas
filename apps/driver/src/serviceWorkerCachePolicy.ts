const CONTENT_HASHED_ASSET = /^\/assets\/[^/]+-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$/;

/**
 * Identifica apenas artefactos de build hashed que já não pertencem ao
 * precache atual. Recursos do utilizador e URLs sem hash nunca entram aqui.
 */
export function obsoleteRuntimeAssetPaths(
  cachedPaths: string[],
  currentPrecachePaths: string[],
): string[] {
  const current = new Set(currentPrecachePaths);
  return cachedPaths.filter(
    (path) => CONTENT_HASHED_ASSET.test(path) && !current.has(path),
  );
}
