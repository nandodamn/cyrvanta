import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { PlaybookLibraryPage } from "../src/PlaybookLibraryPage";

describe("draft playbook safety", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not present or activate a draft as an executable capability", async () => {
    vi.spyOn(api, "getPlaybookDefinitions").mockResolvedValue({
      total: 1,
      items: [
        {
          id: "00000000-0000-0000-0000-000000000002",
          code: "draft-containment",
          title_i18n: { es: "Borrador", en: "Draft" },
          description_i18n: {
            es: "Afirmación no publicada de bloqueo real",
            en: "Unpublished claim of real blocking",
          },
          created_at: "2026-08-01T12:00:00Z",
          latest_version: "1.0.0",
          latest_version_id: "00000000-0000-0000-0000-000000000012",
          latest_artifact_sha256: "a".repeat(64),
          publication_status: "DRAFT",
          engine_type: null,
          binding_status: "PENDING",
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
          readiness_status: "DISABLED",
          blocking_reasons: ["VERSION_NOT_PUBLISHED"],
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

    expect(await screen.findByText("draft-containment")).toBeVisible();
    expect(screen.getByText(/Motor no vinculado|Engine not bound/i)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /Activar playbook|Activate playbook/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Cambiar a Motor n8n|Switch to n8n Engine/i }),
    ).toBeDisabled();

    fireEvent.click(
      screen.getByRole("button", { name: /Ver detalles del playbook|View playbook details/i }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/versión está en borrador|version is a draft/i)).toBeVisible();
    expect(
      within(dialog).queryByText(/Afirmación no publicada|Unpublished claim/i),
    ).not.toBeInTheDocument();
  });
});
