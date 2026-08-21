import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import App from "../src/App";
import { AuthProvider } from "../src/AuthContext";
import "../src/i18n";

describe("protected application", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.documentElement.classList.remove("light");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it("redirects anonymous users to login", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/"]}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("button", { name: /ingresar|sign in/i })).toBeInTheDocument();
  });

  it("shows visible navigation labels and persists the selected theme", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.spyOn(api, "getMe").mockResolvedValue({
      id: "00000000-0000-0000-0000-000000000001",
      tenant_id: "00000000-0000-0000-0000-000000000002",
      email: "demo@example.invalid",
      display_name: "Demo Analyst",
    });
    vi.spyOn(api, "getIncidents").mockResolvedValue([]);
    vi.spyOn(api, "getAlerts").mockResolvedValue([]);
    vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue({
      window_start: "2026-07-31T12:00:00Z",
      window_end: "2026-08-01T12:00:00Z",
      updated_at: "2026-08-01T12:00:00Z",
      source_mode: "EMPTY",
      totals: { alerts: 0, incidents: 0 },
      series: Array.from({ length: 12 }, (_, index) => ({
        bucket_start: new Date(Date.UTC(2026, 6, 31, 12 + index * 2)).toISOString(),
        bucket_end: new Date(Date.UTC(2026, 6, 31, 14 + index * 2)).toISOString(),
        alerts: 0,
        incidents: 0,
      })),
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

    expect(await screen.findByRole("link", { name: /incidentes|incidents/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /playbooks/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /auditoría|audit/i })).toBeVisible();
    // The theme switch lives with the account controls now, one click deeper.
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    // A switch rather than a button that renames itself, so it reports which
    // theme is on rather than which one clicking would bring.
    const themeSwitch = screen.getByRole("switch", { name: /tema|theme/i });
    expect(themeSwitch).toHaveAttribute("aria-checked", "false");
    fireEvent.click(themeSwitch);
    expect(themeSwitch).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement).toHaveClass("light");
    expect(sessionStorage.getItem("theme")).toBe("light");
    expect(sessionStorage.getItem("access_token")).toBeNull();
  });
});
