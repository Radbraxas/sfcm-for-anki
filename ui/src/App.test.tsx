// SPDX-License-Identifier: AGPL-3.0-or-later
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async (command: string) => {
    if (command === "engine_status") return { state: "failed", reason: "protocol mismatch" };
    throw new Error(`unexpected ${command}`);
  }),
}));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async () => () => {}) }));

const { App } = await import("./App");

it("shows why the engine stopped", async () => {
  render(<App />);
  expect(await screen.findByText("protocol mismatch")).toBeTruthy();
  expect(screen.getByRole("status").textContent).toBe("Engine stopped");
});
