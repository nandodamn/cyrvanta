/**
 * The governed memory screen has to be usable and honest.
 *
 * Usable: the circuit it describes -- record what happened, propose a lesson,
 * have someone else review it -- has to be completable from the screen. It was
 * not: proposing a memory demanded feedback UUIDs and the page never showed a
 * UUID anywhere, so the only way through was to read them out of the database.
 *
 * Honest: what it cannot show and what it is not allowed to show are different
 * facts, and it used to report the second as the first.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import { GovernedMemoryPage } from "../src/GovernedMemoryPage";
import "../src/i18n";

const candidate = (overrides: Partial<api.MemoryCandidate> = {}): api.MemoryCandidate => ({
  id: "00000000-0000-0000-0000-000000000101",
  version_id: "00000000-0000-0000-0000-000000000102",
  version: 1,
  kind: "CASE_NOTE",
  source_type: "HUMAN",
  created_by_user_id: "00000000-0000-0000-0000-000000000103",
  version_author_user_id: "00000000-0000-0000-0000-000000000103",
  version_author_name: "Analista SOC Demo",
  title_es: "Patrón de laboratorio",
  title_en: "Lab pattern",
  statement_es: "Contexto de prueba, sin influencia.",
  statement_en: "Test context, without influence.",
  conditions: {},
  evidence_refs: ["00000000-0000-0000-0000-000000000104"],
  is_synthetic: false,
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
  ...overrides,
});

const entry = (overrides: Partial<api.FeedbackEntry> = {}): api.FeedbackEntry => ({
  id: "00000000-0000-0000-0000-000000000201",
  resource_type: "INCIDENT",
  resource_id: "00000000-0000-0000-0000-000000000202",
  resource_label: "INC-AF8E3CD4 · Acceso anómalo",
  actor_user_id: "00000000-0000-0000-0000-000000000103",
  actor_name: "Analista SOC Demo",
  outcome: "FALSE_POSITIVE",
  reason: "Era una tarea programada.",
  is_synthetic: false,
  occurred_at: "2026-08-01T00:00:00Z",
  created_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

function show(permissions: string[], overrides: Partial<api.MemoryCandidate> = {}) {
  vi.spyOn(api, "getMemoryCandidates").mockResolvedValue([candidate(overrides)]);
  vi.spyOn(api, "getActiveMemory").mockResolvedValue([]);
  vi.spyOn(api, "getMemoryMetrics").mockResolvedValue([]);
  vi.spyOn(api, "getFeedback").mockResolvedValue([entry()]);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <GovernedMemoryPage permissions={new Set(permissions)} />
    </QueryClientProvider>,
  );
}

describe("governed memory", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows provenance and the immutable state history", async () => {
    show(["memory.read"]);
    expect(await screen.findByText("Patrón de laboratorio")).toBeVisible();
    expect(screen.getByText(/sin aprendizaje autónomo/i)).toBeVisible();
    expect(screen.getByText(/candidate_created/)).toBeInTheDocument();
  });

  it("names the author of this version, not of the candidate", async () => {
    // After a correction the two differ, and it is the version's author the
    // separation rules protect against reviewing their own work.
    show(["memory.read"]);
    expect(await screen.findByText("Analista SOC Demo")).toBeVisible();
  });

  it("says an unconditional memory will appear on every incident", async () => {
    // It matches everything by construction. Left unsaid, someone writes one
    // narrow lesson and finds it attached to every case in the tenant.
    show(["memory.read"]);
    expect(await screen.findByText(/todos los incidentes/i)).toBeVisible();
  });

  it("refuses to act on synthetic memory", async () => {
    // The API cannot create it, so this only arrives from a fixture -- which
    // is exactly when a rule about synthetic data needs to still hold.
    show(["memory.read", "memory.propose"], { is_synthetic: true });
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByRole("button", { name: /solicitar revisión/i })).not.toBeInTheDocument();
  });

  it("distinguishes not being allowed to see metrics from there being none", async () => {
    // The page used to ask for metrics as everybody and render the resulting
    // 403 as "no metrics recorded", which told every analyst the SOC had
    // measured nothing.
    show(["memory.read"]);
    fireEvent.click(await screen.findByRole("button", { name: /gobernanza/i }));
    expect(screen.getByText(/no puede ver las métricas/i)).toBeVisible();
    expect(api.getMemoryMetrics).not.toHaveBeenCalled();
  });

  it("lets someone who may read metrics actually fetch them", async () => {
    show(["memory.read", "memory.metrics.read"]);
    fireEvent.click(await screen.findByRole("button", { name: /gobernanza/i }));
    expect(api.getMemoryMetrics).toHaveBeenCalled();
  });

  it("offers the recorded feedback as evidence instead of asking for UUIDs", async () => {
    // This is what makes the circuit completable: the analyst picks the case
    // they remember, not an identifier they have no way to obtain.
    show(["memory.read", "memory.propose", "feedback.create"]);
    fireEvent.click(await screen.findByRole("button", { name: /registrar/i }));
    // Twice: once in the ledger of what has been recorded, once as a choice in
    // the evidence picker. Both are the point.
    expect(await screen.findAllByText("INC-AF8E3CD4 · Acceso anómalo")).toHaveLength(2);
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
    expect(screen.queryByText(/separados por coma/i)).not.toBeInTheDocument();
  });

  it("does not offer forms a role cannot submit", async () => {
    show(["memory.read"]);
    fireEvent.click(await screen.findByRole("button", { name: /registrar/i }));
    expect(screen.getByText(/no puede registrar feedback/i)).toBeVisible();
    expect(screen.getByText(/no puede proponer memoria/i)).toBeVisible();
  });
});
