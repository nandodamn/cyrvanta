import { afterEach, describe, expect, it, vi } from "vitest";

import { getIncidents, getPlaybooks, login } from "../src/api";

describe("bounded list requests", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("sends a bounded search with offset and one lookahead row", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    await getIncidents({
      query: "credential",
      page: 2,
      pageSize: 10,
      includeLookahead: true,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/incidents?limit=11&offset=20&q=credential",
      expect.objectContaining({
        credentials: "include",
      }),
    );
  });

  it("requests a bounded playbook catalog", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [],
            total: 0,
            synchronized: false,
            sync_detail: "api_key_not_configured",
            mode: "live",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    await getPlaybooks({ query: "response", page: 1, pageSize: 10 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/playbooks?limit=10&offset=10&q=response",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
