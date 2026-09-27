import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Regex so this only matches "/api/..." — a plain "/api" string key
      // does a prefix match and would also swallow routes like "/api-access".
      "^/api/": "http://localhost:8000",
    },
  },
});
