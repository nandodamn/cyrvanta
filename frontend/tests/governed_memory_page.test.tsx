import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import { GovernedMemoryPage } from "../src/GovernedMemoryPage";
import "../src/i18n";

describe("governed memory", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows provenance, synthetic blocking, and immutable state history", async () => {
    const candidate: api.MemoryCandidate = {
      id: "00000000-0000-0000-0000-000000000101",
      version_id: "00000000-0000-0000-0000-000000000102",
      version: 1,
      kind: "CASE_NOTE",
      source_type: "HUMAN",
      created_by_user_id: "00000000-0000-0000-0000-000000000103",
      title_es: "Patrón de laboratorio",
      title_en: "Lab pattern",
      statement_es: "Contexto sintético, sin influencia.",
      statement_en: "Synthetic context, without influence.",
      conditions: {},
      evidence_refs: ["00000000-0000-0000-0000-000000000104"],
      is_synthetic: true,
      valid_from: "2026-08-01T00:00:00Z",
      valid_until: "2026-08-31T00:00:00Z",
      status: "DRAFT",
      reviews: [],
      state_history: [
        {
          id: "00000000-0000-0000-0000-000000000105",
          actor_user_id: "00000000-0000-0000-0000-000000000103",
          from_status: null,
          to_status: "DRAFT",
          reason: "candidate_created",
          occurred_at: "2026-08-01T00:00:00Z",
        },
      ],
      created_at: "2026-08-01T00:00:00Z",
    };
    vi.spyOn(api, "getMemoryCandidates").mockResolvedValue([candidate]);
    vi.spyOn(api, "getActiveMemory").mockResolvedValue([]);
    vi.spyOn(api, "getMemoryMetrics").mockResolvedValue([]);

    render(
      <QueryClientProvider client={new QueryClient()}>
        <GovernedMemoryPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Patrón de laboratorio")).toBeVisible();
    expect(screen.getByText(/sintético.*activación prohibida/i)).toBeVisible();
    expect(screen.getByText(/sin aprendizaje autónomo/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /solicitar revisión/i })).not.toBeInTheDocument();
  });
});
