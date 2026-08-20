import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import App from "../src/App";
import { AuthProvider } from "../src/AuthContext";
import "../src/i18n";

function signedInAs(roles: { code: string; name: string }[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: "synthetic", token_type: "bearer" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.spyOn(api, "getMe").mockResolvedValue({
    id: "00000000-0000-0000-0000-000000000001",
    tenant_id: "00000000-0000-0000-0000-000000000002",
    email: "quien@example.invalid",
    display_name: "Quien Sea",
    roles,
  });
  vi.spyOn(api, "getIncidents").mockResolvedValue([]);
  vi.spyOn(api, "getAlerts").mockResolvedValue([]);
  vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue({
    window_start: "2026-07-31T12:00:00Z",
    window_end: "2026-08-01T12:00:00Z",
    updated_at: "2026-08-01T12:00:00Z",
    source_mode: "EMPTY",
    totals: { alerts: 0, incidents: 0 },
    series: [],
  });

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the signed-in person's role is visible", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("names every role the session holds", async () => {
    // Every one of them: holding two is allowed, and that is exactly the case
    // worth seeing, because it concentrates duties the product separates.
    signedInAs([
      { code: "soc-analyst", name: "Analista SOC" },
      { code: "soc-supervisor", name: "Supervisor SOC" },
    ]);

    expect(await screen.findByText("Analista SOC · Supervisor SOC")).toBeVisible();
  });

  it("says so when the session holds no role at all", async () => {
    // Not a cosmetic gap: such a user can sign in and do nothing, which is how
    // one of them went unnoticed in this very deployment.
    signedInAs([]);

    expect(await screen.findByText(/sin rol asignado|no role assigned/i)).toBeVisible();
  });
});
