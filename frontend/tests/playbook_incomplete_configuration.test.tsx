import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { PlaybookLibraryPage } from "../src/PlaybookLibraryPage";

/**
 * A playbook whose production configuration is incomplete is present in the
 * catalog but is NOT an available capability: it must read as disabled and must
 * not be activatable, so an operator can never arm a response that would fail
 * the moment an incident needs it.
 */
describe("incompletely configured playbook", () => {
  afterEach(() => vi.restoreAllMocks());

  it("is shown disabled and cannot be activated or engine-switched", async () => {
    vi.spyOn(api, "getPlaybookDefinitions").mockResolvedValue({
      total: 1,
      items: [
        {
          id: "00000000-0000-0000-0000-000000000003",
          code: "notify-critical-incident",
          title_i18n: { es: "Notificación urgente", en: "Urgent notification" },
          description_i18n: { es: "Notifica al SOC", en: "Notifies the SOC" },
          created_at: "2026-08-01T12:00:00Z",
          latest_version: "1.0.0",
          latest_version_id: "00000000-0000-0000-0000-000000000013",
          latest_artifact_sha256: "b".repeat(64),
          // Published and bound, but its connector is not usable yet.
          publication_status: "PUBLISHED",
          engine_type: "NATIVE",
          binding_status: "SYNCHRONIZED",
          binding_active: false,
          execution_mode: "LIVE",
          impact: "MEDIUM",
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
          last_execution_status: null,
          last_executed_at: null,
          readiness_status: "CONFIGURATION_REQUIRED",
          blocking_reasons: [
            "PLAYBOOK_CONFIGURATION_REQUIRED",
            "ACTION_CREDENTIAL_UNVERIFIED:notification.send",
          ],
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

    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <PlaybookLibraryPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("notify-critical-incident")).toBeVisible();

    // Reads as disabled rather than advertising a readiness it does not have,
    // and the card itself is muted.
    expect(container.querySelector(".playbook-disabled-badge")).not.toBeNull();
    expect(container.querySelector("article.playbook-card-disabled")).not.toBeNull();
    expect(screen.queryByText("READY")).toBeNull();

    // Cannot be armed, by either route.
    expect(
      screen.getByRole("button", { name: /Activar playbook|Activate playbook/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Cambiar a Motor n8n|Switch to n8n Engine/i }),
    ).toBeDisabled();

    // States exactly which connector is missing, not just "configuration required".
    expect(screen.getByText(/notification\.send/)).toBeVisible();
  });
});
