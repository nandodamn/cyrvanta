import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { VerifiedIntegrationsPage } from "../src/VerifiedIntegrationsPage";


// A routed page: it reads the connector to prefill from the query string when
// a playbook step sends the operator here, so it needs a router in tests too.
function renderPage(route = "/integrations") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[route]}>
        <VerifiedIntegrationsPage />
      </MemoryRouter>
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

  it("opens on the connector a playbook step asked for", async () => {
    // Arriving from a step with no usable connection: the form has to land on
    // that connector already named, or the operator restarts the task here.
    vi.spyOn(api, "getIntegrationConnections").mockResolvedValue([]);

    renderPage("/integrations?nuevo=HTTP_ALLOWLISTED&nombre=Fuente%20de%20Threat%20Intelligence");

    const nameField = await screen.findByDisplayValue("Fuente de Threat Intelligence");
    expect(nameField).toBeVisible();
    const connectorField = screen.getByDisplayValue("HTTP_ALLOWLISTED");
    expect(connectorField).toBeVisible();
  });

  it("ignores a connector it does not support", async () => {
    vi.spyOn(api, "getIntegrationConnections").mockResolvedValue([]);

    renderPage("/integrations?nuevo=NOT_A_CONNECTOR&nombre=Cualquiera");

    await screen.findByText(/No hay conexiones configuradas/i);
    expect(screen.queryByDisplayValue("Cualquiera")).toBeNull();
  });
});
