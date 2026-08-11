import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const dockerfile = readFileSync(resolve(process.cwd(), "Dockerfile"), "utf-8");
const viteConfig = readFileSync(resolve(process.cwd(), "vite.config.ts"), "utf-8");
const packageJson = JSON.parse(
  readFileSync(resolve(process.cwd(), "package.json"), "utf-8"),
) as {
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
};
const packageLock = JSON.parse(
  readFileSync(resolve(process.cwd(), "package-lock.json"), "utf-8"),
) as { lockfileVersion: number };

describe("frontend supply chain", () => {
  it("builds reproducibly from immutable base images and the committed lockfile", () => {
    expect(dockerfile).toContain(
      "FROM node:22.22.0-alpine@sha256:e4bf2a82ad0a4037d28035ae71529873c069b13eb0455466ae0bc13363826e34 AS build",
    );
    expect(dockerfile).toContain(
      "FROM nginx:1.27.3-alpine@sha256:814a8e88df978ade80e584cc5b333144b9372a8e3c98872d07137dbf3b44d0e4",
    );
    expect(dockerfile).toContain("COPY package.json package-lock.json ./");
    expect(dockerfile).toContain("RUN npm ci --ignore-scripts");
    expect(dockerfile).not.toContain("RUN npm install");
    expect(packageLock.lockfileVersion).toBe(3);
    expect(viteConfig).toContain("function manualChunks(id: string)");
    expect(viteConfig).toContain("output: { manualChunks }");
    expect(viteConfig).not.toContain("manualChunks: {");
  });

  it("pins the corrected router and build toolchain versions", () => {
    expect(packageJson.dependencies["react-router-dom"]).toBe("7.18.2");
    expect(packageJson.devDependencies.vite).toBe("8.2.1");
    expect(packageJson.devDependencies.vitest).toBe("4.1.10");
    expect(packageJson.devDependencies.eslint).toBe("9.39.5");
    expect(packageJson.devDependencies["@vitejs/plugin-react"]).toBe("6.0.5");
  });
});
