import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");

describe("route loading boundaries", () => {
  it("loads modular administration pages on demand behind an accessible fallback", () => {
    for (const moduleName of [
      "ApiKeysPage",
      "GovernedMemoryPage",
      "PlaybookLibraryPage",
      "VerifiedIntegrationsPage",
    ]) {
      expect(app).toContain(`import("./${moduleName}")`);
      expect(app).not.toContain(`from "./${moduleName}";`);
    }
    expect(app).toContain("<Suspense fallback={<RouteLoadingFallback />}>");
    expect(app).toContain('<main className="center" role="status">');
  });
});
