import { defineConfig } from "vitest/config";
import path from "path";

// esbuild transforms JSX with the automatic runtime so source files don't
// need an explicit `import React`. Matches Next.js 14 defaults.
export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
