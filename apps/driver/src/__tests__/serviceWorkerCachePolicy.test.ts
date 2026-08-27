import { describe, expect, it } from "vitest";
import { obsoleteRuntimeAssetPaths } from "../serviceWorkerCachePolicy";

describe("política do cache runtime da PWA", () => {
  it("remove bundles hashed antigos e preserva os artefactos do precache atual", () => {
    expect(
      obsoleteRuntimeAssetPaths(
        [
          "/assets/index-tVgRH7eW.js",
          "/assets/index-GP13naLz.js",
          "/assets/index-DoOAvywB.css",
          "/logo.png",
        ],
        [
          "/assets/index-GP13naLz.js",
          "/assets/index-DoOAvywB.css",
          "/index.html",
        ],
      ),
    ).toEqual(["/assets/index-tVgRH7eW.js"]);
  });

  it("não elimina recursos sem hash que podem ser dados offline do utilizador", () => {
    expect(
      obsoleteRuntimeAssetPaths(
        ["/assets/manual.js", "/photo-driver.png", "/api/v1/driver/bootstrap"],
        [],
      ),
    ).toEqual([]);
  });
});
