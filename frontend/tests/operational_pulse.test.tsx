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
      source_mode: "LIVE",
      totals: { alerts: 3, incidents: 1 },
      series: Array.from({ length: 12 }, (_, index) => ({
        bucket_start: new Date(Date.UTC(2026, 6, 31, 12 + index * 2)).toISOString(),
        bucket_end: new Date(Date.UTC(2026, 6, 31, 14 + index * 2)).toISOString(),
        alerts: index === 11 ? 3 : 0,
        incidents: index === 11 ? 1 : 0,
      })),
    });

    renderPulse();

    expect(await screen.findByText(/real|live/i)).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(12);
    expect(screen.getByText(/última actualización|last updated/i)).toBeVisible();
    expect(screen.getByText("3")).toBeVisible();
    expect(screen.getByText("1")).toBeVisible();
  });
});

describe("operational pulse readability", () => {
  afterEach(() => vi.restoreAllMocks());

  function skewed() {
    // The real shape of this data: one ingestion burst holding 94% of the day.
    const volumes = [0, 5, 14, 0, 0, 0, 0, 6, 0, 0, 1034, 41];
    return {
      window_start: "2026-08-18T15:00:00Z",
      window_end: "2026-08-19T15:00:00Z",
      updated_at: "2026-08-19T15:02:51Z",
      source_mode: "LIVE" as const,
      totals: { alerts: 1100, incidents: 0 },
      series: volumes.map((alerts, index) => ({
        bucket_start: new Date(Date.UTC(2026, 7, 18, 15 + index * 2)).toISOString(),
        bucket_end: new Date(Date.UTC(2026, 7, 18, 17 + index * 2)).toISOString(),
        alerts,
        incidents: 0,
      })),
    };
  }

  it("never draws a bar for a quiet bucket that could pass for activity", async () => {
    vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue(skewed());
    renderPulse();

    const bars = await screen.findAllByRole("listitem");
    expect(bars).toHaveLength(12);

    const empty = bars.filter((bar) => bar.className.includes("is-empty"));
    const active = bars.filter((bar) => !bar.className.includes("is-empty"));
    expect(empty).toHaveLength(7);
    expect(active).toHaveLength(5);
    // A quiet bucket has no bar at all; every real one keeps a visible floor,
    // so the smallest bucket of the day cannot be mistaken for silence.
    active.forEach((bar) => expect(bar.style.height).toContain("max("));
  });

  it("states the scale, because one busy bucket sets it for all the others", async () => {
    vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue(skewed());
    renderPulse();

    expect(await screen.findByText(/1034/)).toBeVisible();
  });

  it("does not label the bars with categories they never encoded", async () => {
    vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue(skewed());
    renderPulse();

    await screen.findAllByRole("listitem");
    expect(screen.queryByText(/^detecciones$|^detections$/i)).toBeNull();
    expect(screen.getByText(/2 horas de actividad|2 hours of activity/i)).toBeVisible();
  });
});
