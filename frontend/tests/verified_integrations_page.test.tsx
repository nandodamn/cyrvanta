import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { VerifiedIntegrationsPage } from "../src/VerifiedIntegrationsPage";


function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <VerifiedIntegrationsPage />
    </QueryClientProvider>,
  );
}


describe("verified integrations page", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders only health records returned by the backend", async () => {
    vi.spyOn(api, "getIntegrationHealth").mockResolvedValue([
      { code: "wazuh", mode: "live", healthy: true, detail: "reachable" },
      { code: "ollama", mode: "disabled", healthy: false, detail: "disabled" },
    ]);

    renderPage();

    expect(await screen.findByText("wazuh")).toBeVisible();
    expect(screen.getByText("ollama")).toBeVisible();
    expect(screen.queryByText(/9 configuradas|9 configured/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AES-256-GCM/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ServiceNow/i)).not.toBeInTheDocument();
  });

  it("shows an explicit empty state instead of connector cards", async () => {
    vi.spyOn(api, "getIntegrationHealth").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText(/todavía no hay datos|there is no data/i)).toBeVisible();
    expect(screen.queryByText("wazuh")).not.toBeInTheDocument();
  });
});
