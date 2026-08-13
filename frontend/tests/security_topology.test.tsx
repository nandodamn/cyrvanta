import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
    expect(screen.queryByText("192.168.1.1")).not.toBeInTheDocument();
    expect(screen.queryByText(/PaloAlto/i)).not.toBeInTheDocument();
  }, 20000);
});
