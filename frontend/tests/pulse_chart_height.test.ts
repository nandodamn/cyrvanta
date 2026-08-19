import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const styles = readFileSync(resolve(process.cwd(), "src", "styles.css"), "utf-8");

function block(selector: string): string {
  // Anchored to the start of a line: ".signal-grid {" is also a substring of
  // ".pulse-panel .signal-grid {", and matching that one instead would assert
  // against the wrong rule.
  const start = styles.indexOf(`
${selector} {`);
  expect(start, `${selector} is missing from styles.css`).toBeGreaterThan(-1);
  // Comments are stripped: the rule explains in prose why it is not `flex: 1`,
  // and asserting over that prose would match the very thing being forbidden.
  return styles.slice(start, styles.indexOf("}", start)).replace(/\/\*[\s\S]*?\*\//g, "");
}

describe("operational pulse chart height", () => {
  // jsdom performs no layout, so no rendering test can catch this: the chart
  // collapsed to nothing and every test still passed. The bar heights are
  // percentages, which resolve to zero unless the container height is real,
  // so the two declarations that keep it real are asserted directly.
  it("keeps a definite height that flex sizing cannot override", () => {
    const grid = block(".signal-grid");
    expect(grid).toMatch(/height:\s*\d+px/);
    // `flex: 1` inside the column-flex panel means flex-basis 0% on the
    // height, which silently wins over that height and collapses the chart.
    expect(grid).not.toMatch(/flex:\s*1\b/);
    expect(grid).toMatch(/flex:\s*none/);
  });

  it("draws an empty bucket as a baseline rather than a stub bar", () => {
    const empty = block(".signal-grid i.is-empty");
    expect(empty).toMatch(/height:\s*0/);
    expect(empty).toMatch(/border-bottom/);
  });
});
