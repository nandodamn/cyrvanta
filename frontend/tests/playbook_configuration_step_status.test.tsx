import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { PlaybookConfigurationModal } from "../src/PlaybookConfigurationModal";

/**
 * A multi-step playbook is blocked by specific steps, not by all of them.
 * Describing every step as pending sent the operator to fix a connection that
 * was already active and verified, while the step actually holding the
 * playbook back stayed invisible until each one was opened in turn.
 */

function playbook(blocking: string[]): api.PlaybookDefinition {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    code: "contain-and-document-incident",
    title_i18n: { es: "Contención de host", en: "Host containment" },
    description_i18n: { es: "Aísla y documenta", en: "Isolates and documents" },
    created_at: "2026-08-01T12:00:00Z",
    latest_version: "1.0.1",
    latest_version_id: "00000000-0000-0000-0000-000000000011",
    latest_artifact_sha256: "a".repeat(64),
    publication_status: "PUBLISHED",
    engine_type: "NATIVE",
    binding_status: "PENDING",
    binding_active: false,
    execution_mode: "LIVE",
    impact: "MEDIUM",
    required_parameters: [],
    credential_aliases: [],
    required_actions: ["host.isolate", "incident.report.generate", "incident.status.transition"],
    target_incident_types: [],
    mitre_codes: [],
    rollback_supported: true,
    rollback_action_code: "host.restore",
    rollback_guidance_i18n: null,
    automation_policy_i18n: null,
    approval_mode: "SINGLE",
    last_execution_status: null,
    last_executed_at: null,
    readiness_status: "CONFIGURATION_REQUIRED",
    blocking_reasons: blocking,
  } as api.PlaybookDefinition;
}

function renderModal(blocking: string[]) {
  vi.spyOn(api, "getPlaybookActions").mockResolvedValue([
    {
      code: "host.isolate",
      version: "1.0.0",
      modes: ["LIVE"],
      impact: "HIGH",
      timeout_seconds: 30,
      retry_safe: false,
      cancellable: false,
      egress: "HTTPS",
    },
    {
      code: "incident.report.generate",
      version: "1.0.0",
      modes: ["LIVE"],
      impact: "MEDIUM",
      timeout_seconds: 30,
      retry_safe: false,
      cancellable: false,
      egress: "SMTP",
    },
  ]);
  vi.spyOn(api, "getIntegrationConnections").mockResolvedValue([]);
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PlaybookConfigurationModal playbook={playbook(blocking)} onClose={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("playbook step configuration status", () => {
  afterEach(() => vi.restoreAllMocks());

  it("names the step that is blocking and leaves the satisfied ones alone", async () => {
    renderModal([
      "PLAYBOOK_CONFIGURATION_REQUIRED",
      "ACTION_CREDENTIAL_MISSING:incident.report.generate",
    ]);

    // The report step is the one to fix, with the reason spelled out.
    const summary = await screen.findByText(/Falta un paso/i);
    expect(summary.textContent).toMatch(/sin conexión asociada/i);
    // Wazuh isolation is already satisfied, so it must not be described as
    // waiting on a connection that is in fact active and verified.
    expect(screen.queryByText(/Falta la conexión Wazuh/i)).toBeNull();
    expect(await screen.findByText(/Listo mediante la conexión Wazuh/i)).toBeVisible();
  });

  it("treats a reason it does not recognise as blocking", async () => {
    // A new backend reason must not read as ready just because this file has
    // not been taught about it yet.
    renderModal(["PLAYBOOK_CONFIGURATION_REQUIRED", "ACTION_SOMETHING_NEW:host.isolate"]);

    expect(await screen.findByText(/Falta la conexión Wazuh/i)).toBeVisible();
    const summary = screen.getByText(/Falta un paso/i);
    expect(summary.textContent).toMatch(/requiere atención/i);
  });

  it("says nothing is pending when every step is satisfied", async () => {
    renderModal([]);

    expect(await screen.findByText(/Listo mediante la conexión Wazuh/i)).toBeVisible();
    expect(screen.queryByText(/Falta/i)).toBeNull();
  });
});
