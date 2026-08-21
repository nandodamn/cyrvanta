/**
 * Every colour must come from the palette.
 *
 * CSS makes this failure silent: `var(--border, #1f2937)` compiles, renders,
 * and looks plausible, but `--border` was never declared -- so the fallback
 * wins, off-palette and frozen. Four panels were built that way and only
 * surfaced when one of them dissolved into the sidebar in the dark theme,
 * because the invented tone happened to match it.
 *
 * The theme switch makes it worse than an inconsistency: a literal colour
 * cannot follow `:root.light`, so anything hardcoded stays put when the rest
 * of the interface flips, and text goes unreadable on its own background.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src", "styles.css"), "utf-8");

const declared = new Set(Array.from(css.matchAll(/^\s*(--[\w-]+)\s*:/gm), (m) => m[1]));

describe("colours come from the palette", () => {
  it("declares every custom property it reads", () => {
    const used = new Set(Array.from(css.matchAll(/var\(\s*(--[\w-]+)/g), (m) => m[1]));
    expect([...used].filter((name) => !declared.has(name))).toEqual([]);
  });

  it("declares the same properties in both themes", () => {
    // A property defined only in the dark block keeps its dark value when the
    // light theme is on, which is the same failure by another route.
    const block = (selector: string) => {
      const start = css.indexOf(selector);
      return new Set(
        Array.from(
          css.slice(start, css.indexOf("}", start)).matchAll(/(--[\w-]+)\s*:/g),
          (m) => m[1],
        ),
      );
    };
    const dark = block(":root {");
    const light = block(":root.light {");
    expect([...dark].filter((name) => !light.has(name))).toEqual([]);
  });

  it("does not fall back to a literal colour behind a palette variable", () => {
    // A fallback is how an undeclared name goes unnoticed: it renders, so
    // nothing complains. If the property exists the fallback is dead weight;
    // if it does not, the fallback is a hardcoded colour in disguise.
    const fallbacks = Array.from(
      css.matchAll(/var\(\s*--[\w-]+\s*,\s*(#[0-9a-fA-F]{3,8}|rgb|hsl)/g),
      (m) => m[0],
    );
    expect(fallbacks).toEqual([]);
  });
});
