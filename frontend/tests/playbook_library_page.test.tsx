import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
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
          description_i18n: { es: "Acción real", en: "Real action" },
          created_at: "2026-08-01T12:00:00Z",
          latest_version: "2.1.0",
          latest_version_id: "00000000-0000-0000-0000-000000000011",
          latest_artifact_sha256: "b".repeat(64),
          publication_status: "PUBLISHED",
          engine_type: "NATIVE",
          binding_status: "SYNCHRONIZED",
          binding_active: true,
          execution_mode: "LIVE",
          impact: "LOW",
          required_parameters: [],
          credential_aliases: [],
          required_actions: ["notification.send"],
          target_incident_types: [],
          mitre_codes: [],
          rollback_supported: false,
          rollback_action_code: null,
          rollback_guidance_i18n: null,
          automation_policy_i18n: null,
          approval_mode: "SINGLE",
          last_execution_status: "SUCCEEDED",
          last_executed_at: "2026-08-01T12:10:00Z",
          readiness_status: "READY",
          blocking_reasons: [],
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
    // "Cyrvanta Native" is stated once for the whole library, in the page header,
    // rather than repeated on every card as a constant fact.
    expect(screen.getAllByText("Cyrvanta Native").length).toBeGreaterThan(0);
    // The card keeps only the facts that actually differ between playbooks.
    expect(screen.getByText("SYNCHRONIZED")).toBeVisible();
    expect(screen.getByText("SUCCEEDED")).toBeVisible();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
    expect(screen.queryByText("MEDIUM")).not.toBeInTheDocument();
    expect(screen.queryByText("PUBLISHED")).not.toBeInTheDocument();
    expect(screen.getAllByText(/n8n opcional|optional n8n/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Sin mappings sustentados|No supported mappings/i)).toBeVisible();
    expect(screen.queryByText("T1078")).not.toBeInTheDocument();
    expect(screen.queryByText(/Rollback habilitado|Rollback enabled/i)).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Ver detalles del playbook|View playbook details/i }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/Sin mappings sustentados|No supported mappings/i),
    ).toBeVisible();
    expect(
      within(dialog).getByText(/No existe un procedimiento|No reversal procedure is published/i),
    ).toBeVisible();
    expect(within(dialog).queryByText("T1078")).not.toBeInTheDocument();
    expect(
      within(dialog).queryByText(/LISTO PARA PRODUC|READY FOR PRODUCTION/i),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).queryByText(/HABILITADO Y OPERATIVO|ENABLED AND OPERATIONAL/i),
    ).not.toBeInTheDocument();
  });
});
