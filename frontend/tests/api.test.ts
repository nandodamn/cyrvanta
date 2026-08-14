import { afterEach, describe, expect, it, vi } from "vitest";

import {
  proposePlaybookAction,
  getClaims,
  getCorrelations,
  getIncidents,
  getPlaybooks,
  login,
} from "../src/api";

describe("bounded list requests", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("sends a bounded search with offset and one lookahead row", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    await getIncidents({
      query: "credential",
      page: 2,
      pageSize: 10,
      includeLookahead: true,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/incidents?limit=11&offset=20&q=credential",
      expect.objectContaining({
        credentials: "include",
      }),
    );
  });

  it("requests a bounded playbook catalog", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [],
            total: 0,
            synchronized: false,
            sync_detail: "api_key_not_configured",
            mode: "live",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    await getPlaybooks({ query: "response", page: 1, pageSize: 10 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/playbooks?limit=10&offset=10&q=response",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("validates and requests a bounded claim ledger projection", async () => {
    const incidentId = "00000000-0000-0000-0000-000000000010";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "00000000-0000-0000-0000-000000000011",
              incident_id: incidentId,
              claim_type: "INFERENCE",
              statement: "Synthetic inference",
              language_code: "en",
              confidence: 0.65,
              origin_type: "RULE",
              origin_actor_user_id: null,
              origin_code: "incident-analysis",
              origin_version: "1",
              provider: null,
              model: null,
              explanation: "Evidence-bounded test",
              validation_criteria: null,
              missing_evidence: [],
              is_simulated: false,
              state: "PROPOSED",
              evidence: [
                {
                  evidence_type: "INCIDENT",
                  evidence_id: incidentId,
                  relationship: "SUPPORTS",
                  evidence_sha256: null,
                },
              ],
              presentations: { es: "Inferencia sintética" },
              created_at: "2026-07-28T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    const claims = await getClaims(incidentId);

    expect(claims).toHaveLength(1);
    expect(claims[0].state).toBe("PROPOSED");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `/api/v1/incidents/${incidentId}/claims?limit=25`,
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("validates a bounded deterministic correlation projection", async () => {
    const incidentId = "00000000-0000-0000-0000-000000000020";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "00000000-0000-0000-0000-000000000021",
              incident_id: incidentId,
              rule_code: "credential-attack",
              rule_version: "2",
              score: 85,
              threshold: 85,
              result_type: "MATCHED",
              explanation: "deterministic",
              is_simulated: false,
              window_start: "2026-07-28T12:00:00Z",
              window_end: "2026-07-28T12:10:00Z",
              claim_id: "00000000-0000-0000-0000-000000000022",
              created_at: "2026-07-28T12:05:00Z",
              members: [],
              factors: [
                {
                  factor_code: "exact_source_ip",
                  matched: true,
                  weight: 40,
                  contribution: 40,
                  explanation_code: "correlation.factor.exact_source_ip",
                },
              ],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    const correlations = await getCorrelations(incidentId);

    expect(correlations[0].score).toBe(85);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `/api/v1/incidents/${incidentId}/correlations?limit=25`,
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("creates a tenant-scoped proposal with an idempotency key", async () => {
    const incidentId = "00000000-0000-0000-0000-000000000030";
    const proposalId = "00000000-0000-0000-0000-000000000031";
    const requesterId = "00000000-0000-0000-0000-000000000032";
    const approvalId = "00000000-0000-0000-0000-000000000033";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "synthetic-access-token",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: proposalId,
            incident_id: incidentId,
            requester_user_id: requesterId,
            action_type: "notify-critical-incident",
            impact: "MODERATE",
            requested_mode: "HUMAN_APPROVAL",
            workflow_id: "notify-critical-incident",
            workflow_version: "1.0.0",
            targets: [incidentId],
            parameters: {},
            evidence_refs: [],
            incident_version: 1,
            is_simulated: false,
            fingerprint: "a".repeat(64),
            status: "AWAITING_APPROVAL",
            evaluation_outcome: "APPROVAL_REQUIRED",
            reason_codes: ["HUMAN_APPROVAL_REQUIRED"],
            approval_request_id: approvalId,
            required_approvals: 1,
            approval_status: "PENDING",
            approval_expires_at: "2026-07-29T12:30:00Z",
            decisions: [],
            authorization: null,
            created_at: "2026-07-29T12:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await login("tenant-demo", "demo@example.invalid", "not-a-real-password", false);
    const proposal = await proposePlaybookAction(incidentId, {
      code: "notify-critical-incident",
      latest_version: "1.0.0",
      impact: "MODERATE",
      approval_mode: "SINGLE",
    });

    expect(proposal.status).toBe("AWAITING_APPROVAL");
    const request = fetchMock.mock.calls[1][1] as RequestInit;
    expect(new Headers(request.headers).get("Idempotency-Key")).toBe(
      `response-proposal-${incidentId}-notify-critical-incident-1.0.0`,
    );
  });
});
