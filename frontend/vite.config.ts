import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const target = process.env.VITE_API_TARGET || "http://localhost:8080";

const vendorChunks: ReadonlyArray<readonly [string, readonly string[]]> = [
  ["vendor-react", ["react", "react-dom", "react-router-dom"]],
  ["vendor-query", ["@tanstack/react-query"]],
  ["vendor-forms", ["@hookform/resolvers", "react-hook-form", "zod"]],
  ["vendor-i18n", ["i18next", "react-i18next"]],
];

function manualChunks(id: string): string | undefined {
  const normalizedId = id.split("\\").join("/");
  return vendorChunks.find(([, packages]) =>
    packages.some((packageName) =>
      normalizedId.includes(`/node_modules/${packageName}/`),
    ),
  )?.[0];
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: { manualChunks },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
      },
    },
  },
});
