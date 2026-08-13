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

  it("renders configured integration connections with parameters", async () => {
    vi.spyOn(api, "getIntegrationConnections").mockResolvedValue([
      {
        id: "11111111-1111-1111-1111-111111111111",
        connector_type: "WAZUH",
        name: "Wazuh SIEM Local Manager",
        status: "active",
        configured: true,
        last_health_check_at: "2026-08-13T16:00:00Z",
        last_error_code: null,
        capabilities: ["findings.ingest"],
        sanitized_parameters: {
          base_url: "https://wazuh-manager:55000",
          username: "wazuh-api",
          password: "••••••••",
        },
      },
    ]);

    renderPage();

    expect(await screen.findByText("Wazuh SIEM Local Manager")).toBeVisible();
    expect(screen.getByText("https://wazuh-manager:55000")).toBeVisible();
    expect(screen.getByText("wazuh-api")).toBeVisible();
    expect(screen.getByText("findings.ingest")).toBeVisible();
  });

  it("shows informative empty state when no connections are configured", async () => {
    vi.spyOn(api, "getIntegrationConnections").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText(/No hay conexiones configuradas/i)).toBeVisible();
    expect(screen.getByText(/Plantilla Wazuh SIEM/i)).toBeVisible();
  });
});
