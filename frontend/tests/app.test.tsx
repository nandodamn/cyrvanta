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
    const themeButton = screen.getByRole("button", { name: /tema claro|light theme/i });
    fireEvent.click(themeButton);
    expect(document.documentElement).toHaveClass("light");
    expect(sessionStorage.getItem("theme")).toBe("light");
    expect(sessionStorage.getItem("access_token")).toBeNull();
  });
});
