import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { PlaybookLibraryPage } from "../src/PlaybookLibraryPage";

describe("native playbook library", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows native as default and n8n as optional per binding", async () => {
    vi.spyOn(api, "getPlaybookDefinitions").mockResolvedValue({
      total: 1,
      items: [
        {
          id: "00000000-0000-0000-0000-000000000001",
          code: "notify-critical-incident",
          title_i18n: { es: "Notificar incidente", en: "Notify incident" },
          description_i18n: { es: "Simulado", en: "Simulated" },
          created_at: "2026-08-01T12:00:00Z",
          latest_version: "2.1.0",
          publication_status: "PUBLISHED",
          engine_type: "NATIVE",
          binding_status: "SYNCHRONIZED",
          binding_active: true,
          execution_mode: "SIMULATED",
          impact: "LOW",
          required_parameters: [],
          credential_aliases: [],
          target_incident_types: [],
          mitre_codes: [],
          rollback_supported: false,
          rollback_target_code: null,
          rollback_guidance_i18n: null,
          automation_policy_i18n: null,
          approval_mode: "AUTOMATIC",
          last_execution_status: "SUCCEEDED",
          last_executed_at: "2026-08-01T12:10:00Z",
        },
      ],
    });
    vi.spyOn(api, "getPlaybooks").mockResolvedValue({
      items: [],
      total: 0,
      synchronized: false,
      sync_detail: "disabled",
      mode: "disabled",
    });
    vi.spyOn(api, "getPlaybookManagement").mockRejectedValue(new Error("disabled"));

    render(
      <QueryClientProvider client={new QueryClient()}>
        <PlaybookLibraryPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("notify-critical-incident")).toBeVisible();
    expect(screen.getAllByText("Cyrvanta Native").length).toBeGreaterThan(0);
    expect(screen.getByText("SIMULATED")).toBeVisible();
    expect(screen.getByText("SYNCHRONIZED")).toBeVisible();
    expect(screen.getByText("SUCCEEDED")).toBeVisible();
    expect(screen.getAllByText(/n8n opcional|optional n8n/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Sin mappings sustentados|No supported mappings/i)).toBeVisible();
    expect(screen.queryByText("T1078")).not.toBeInTheDocument();
    expect(screen.queryByText(/Rollback habilitado|Rollback enabled/i)).not.toBeInTheDocument();
  });
});
