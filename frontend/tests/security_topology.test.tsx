import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { SecurityTopologyPanel } from "../src/SecurityTopologyPanel";

describe("security topology", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows an explicit empty state without fallback nodes or LIVE label", async () => {
    vi.spyOn(api, "getNetworkTopology").mockResolvedValue({
      tenant_id: "00000000-0000-0000-0000-000000000001",
      nodes: [],
      edges: [],
      updated_at: "2026-08-11T12:00:00Z",
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <SecurityTopologyPanel />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/todavía no hay datos|there is no data/i)).toBeVisible();
    expect(screen.queryByText(/LIVE/i)).not.toBeInTheDocument();
  }, 20000);

  it("renders 3 operational zones and consolidated multi-IP host services", async () => {
    const mockNodes: api.TopologyNode[] = [
      {
        id: "gw-01",
        name: "Cyrvanta API Gateway",
        type: "GATEWAY",
        category: "CYRVANTA_CORE",
        ip_address: "10.0.0.1",
        ip_addresses: ["10.0.0.1"],
        services: [{ name: "HTTPS API", port: 443, protocol: "HTTPS", status: "ONLINE" }],
        subnet: "10.0.0.0/24 DMZ",
        status: "ONLINE",
        latency_ms: 2,
        last_ping: "2026-08-13T12:00:00Z",
        active_alerts_count: 0,
        role_description_es: "Gateway perimetral Cyrvanta",
        role_description_en: "Cyrvanta perimeter gateway",
      },
      {
        id: "siem-01",
        name: "Wazuh SIEM Manager",
        type: "SIEM",
        category: "SECURITY_FEED",
        ip_address: "10.0.1.10",
        ip_addresses: ["10.0.1.10"],
        services: [{ name: "Agent Listener", port: 1514, protocol: "TCP", status: "ONLINE" }],
        subnet: "10.0.1.0/24 SecOps",
        status: "ONLINE",
        latency_ms: 5,
        last_ping: "2026-08-13T12:00:00Z",
        active_alerts_count: 0,
        role_description_es: "Gestor central de eventos",
        role_description_en: "Central event manager",
      },
      {
        id: "lab-server-01",
        name: "SRV-APP-PROD-01",
        type: "SERVER",
        category: "MONITORED_ASSET",
        ip_address: "10.0.1.60",
        ip_addresses: ["10.0.1.60", "192.168.10.60"],
        services: [
          { name: "Web ERP Portal", port: 443, protocol: "HTTPS", status: "ONLINE" },
          { name: "Internal API Backend", port: 8080, protocol: "HTTP", status: "ONLINE" },
        ],
        subnet: "10.0.1.0/24 Production",
        status: "ONLINE",
        latency_ms: 3,
        last_ping: "2026-08-13T12:00:00Z",
        active_alerts_count: 1,
        active_alerts: [
          {
            id: "alt-01",
            title: "Suspicious SQL Injection probe",
            severity: "high",
            category: "Web Attack",
            observed_at: "2026-08-13T12:00:00Z",
          },
        ],
        os_info: "Ubuntu Linux 22.04 LTS",
        monitored_by: ["Wazuh Agent #014"],
        role_description_es: "Servidor de aplicaciones consolidado",
        role_description_en: "Consolidated application server",
      },
    ];

    vi.spyOn(api, "getNetworkTopology").mockResolvedValue({
      tenant_id: "00000000-0000-0000-0000-000000000001",
      nodes: mockNodes,
      edges: [],
      updated_at: "2026-08-13T12:00:00Z",
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <SecurityTopologyPanel />
      </QueryClientProvider>,
    );

    // Verify 3 operational zone titles are displayed
    expect(await screen.findByText(/FUENTES DE SEGURIDAD|SECURITY FEEDS/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PLATAFORMA CYRVANTA/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/RED Y ACTIVOS/i).length).toBeGreaterThan(0);

    // Verify consolidated host and its services
    expect(screen.getByText("SRV-APP-PROD-01")).toBeInTheDocument();
    expect(screen.getByText(/10.0.1.60/)).toBeInTheDocument();

    // Switch to table view
    const tableBtn = screen.getByRole("button", { name: /Tabla|Table/i });
    fireEvent.click(tableBtn);

    // Verify host services and IPs are displayed in table view
    expect(screen.getByText(/Web ERP Portal/)).toBeInTheDocument();
    expect(screen.getByText(/Internal API Backend/)).toBeInTheDocument();
  }, 20000);
});
