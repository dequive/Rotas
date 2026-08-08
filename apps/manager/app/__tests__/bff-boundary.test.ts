import { describe, expect, it } from "vitest";

import { bffRequest } from "../lib/bff";

describe("bffRequest boundary", () => {
  it.each(["https://backend/api/v1/trips", "/api/v1/trips"])(
    "rejects non-BFF explicit path %s",
    async (path) => {
      await expect(bffRequest("/api/v1/trips", { path })).rejects.toMatchObject({
        message: "Manager BFF path required.",
        status: 400,
      });
    },
  );
});
