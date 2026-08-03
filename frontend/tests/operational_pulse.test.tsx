import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import "../src/i18n";
import { OperationalPulse } from "../src/OperationalPulse";

function renderPulse() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <OperationalPulse />
    </QueryClientProvider>,
  );
}

describe("operational pulse", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows an explicit empty state without invented bars", async () => {
    vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue({
      window_start: "2026-07-31T12:00:00Z",
      window_end: "2026-08-01T12:00:00Z",
      updated_at: "2026-08-01T12:00:00Z",
      source_mode: "EMPTY",
      totals: { alerts: 0, incidents: 0 },
      series: Array.from({ length: 12 }, (_, index) => ({
        bucket_start: `2026-08-01T${String(index * 2).padStart(2, "0")}:00:00Z`,
        bucket_end: `2026-08-01T${String(index * 2 + 2).padStart(2, "0")}:00:00Z`,
        alerts: 0,
        incidents: 0,
      })),
    });

    renderPulse();

    expect(await screen.findByText(/sin actividad registrada|no activity recorded/i)).toBeVisible();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("renders real totals, buckets, source badge, and update time", async () => {
    vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue({
      window_start: "2026-07-31T12:00:00Z",
      window_end: "2026-08-01T12:00:00Z",
      updated_at: "2026-08-01T12:00:00Z",
      source_mode: "SIMULATED",
      totals: { alerts: 3, incidents: 1 },
      series: Array.from({ length: 12 }, (_, index) => ({
        bucket_start: new Date(Date.UTC(2026, 6, 31, 12 + index * 2)).toISOString(),
        bucket_end: new Date(Date.UTC(2026, 6, 31, 14 + index * 2)).toISOString(),
        alerts: index === 11 ? 3 : 0,
        incidents: index === 11 ? 1 : 0,
      })),
    });

    renderPulse();

    expect(await screen.findByText(/simulad[oa]|simulated/i)).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(12);
    expect(screen.getByText(/última actualización|last updated/i)).toBeVisible();
    expect(screen.getByText("3")).toBeVisible();
    expect(screen.getByText("1")).toBeVisible();
  });
});
