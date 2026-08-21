/**
 * The layout rules that keep content on the screen.
 *
 * These were found by measuring every screen at 320px, 640px, 1280px and 4K in
 * a real browser: the incident list stretched its panel to 1015px inside a
 * 288px phone and put the search and paging controls out of reach, the audit
 * row held five columns at any width, and the login form grew to 1167px on a
 * 4K panel. jsdom performs no layout, so none of that can be re-measured here.
 * What a test can do is hold the specific declarations that fixed it, since
 * each one is a single property that reads as removable to anyone who did not
 * watch the page break without it.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src", "styles.css"), "utf-8");
const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");

const collapsed = css.replace(/\s+/g, " ");

describe("reflow", () => {
  it("pins list and panel columns so a row cannot outgrow its container", () => {
    // A bare `1fr` keeps an automatic minimum equal to its content, so a grid
    // column grows to the widest field and the row hangs out of the box.
    expect(collapsed).toContain(".data-list { display: grid;");
    expect(collapsed).toMatch(/\.data-list \{[^}]*grid-template-columns: minmax\(0, 1fr\)/);
    expect(collapsed).toMatch(/\.panel \{[^}]*grid-template-columns: minmax\(0, 1fr\)/);
  });

  it("never lets a card grid hold a floor wider than a phone", () => {
    // repeat(auto-fill, minmax(320px, 1fr)) keeps its 320px floor even in a
    // 288px container, so every card overflowed by the difference. Smaller
    // floors are fine -- they sit in tracks that collapse at the breakpoint --
    // so this only catches the ones a 320px screen can never satisfy.
    const tooWide = (source: string) =>
      [...source.matchAll(/minmax\((\d+)px, 1fr\)/g)]
        .map((m) => Number(m[1]))
        .filter((px) => px >= 300);
    expect(tooWide(css)).toEqual([]);
    expect(tooWide(app)).toEqual([]);
    expect(css).toContain("minmax(min(320px, 100%), 1fr)");
  });

  it("truncates a long incident title instead of pushing the row off screen", () => {
    // It used to be `white-space: nowrap` inline, which no breakpoint could
    // lift: on a 1280px window one long title gave the whole page a
    // horizontal scrollbar.
    expect(collapsed).toMatch(/\.incident-row-title \{[^}]*text-overflow: ellipsis/);
    expect(app).toContain('className="incident-row-title"');
    expect(app).not.toMatch(/incident\.code\}[\s\S]{0,80}whiteSpace: "nowrap"/);
  });

  it("keeps row layout in CSS, where a breakpoint can reach it", () => {
    // An inline gridTemplateColumns wins over any media query, so the audit
    // row held its five columns at every width.
    expect(app).toContain('className="audit-row"');
    expect(app).not.toContain('gridTemplateColumns: "100px 1.5fr 1.2fr 1fr 160px"');
  });

  it("stops the login form growing past the widest desktop it was drawn for", () => {
    // Everything in that shell is sized in vw, so a 4K panel gave it a
    // 1167px card with text fields over a thousand pixels wide.
    expect(collapsed).toContain("@media (min-width: 1921px)");
    expect(collapsed).toMatch(/@media \(min-width: 1921px\) \{[^}]*\.login-shell/);
  });

  it("gives the moved row layouts enough weight to actually apply", () => {
    // The inline styles these replaced won by being inline. As bare classes
    // they lost to `.data-list article, .data-list a`, which is one point
    // heavier, and both rows silently fell back to the generic four-column
    // template -- the audit date wrapped to a second grid row, and the
    // incident row stopped being flex. Scoping through .data-list restores
    // the precedence the inline styles used to have.
    const selectores = collapsed
      .split("}")
      .map((bloque) => bloque.split("{")[0])
      .filter(Boolean);
    for (const fila of [".audit-row", ".incident-row "]) {
      const declarantes = selectores.filter((s) => s.includes(fila));
      expect(declarantes.length).toBeGreaterThan(0);
      for (const s of declarantes) {
        expect(s).toContain(".data-list");
      }
    }
  });

  it("lets rows wrap only on narrow screens", () => {
    // The wrap belongs to the 640px breakpoint: a desktop row stays on one
    // line, and the components set no inline flex-wrap for it to fight.
    const narrow = css.slice(css.indexOf("@media (max-width: 640px)"));
    expect(narrow).toContain("flex-wrap: wrap");
    expect(narrow).toContain(".data-list .audit-row");
  });
});
