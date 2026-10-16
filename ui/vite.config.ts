// SPDX-License-Identifier: AGPL-3.0-or-later
/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Tauri expects a fixed port and does not want the screen cleared on rebuild.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  envPrefix: ["VITE_", "TAURI_ENV_"],
  build: { target: "es2022", sourcemap: true },
  test: { environment: "jsdom", globals: true },
});
