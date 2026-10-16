// SPDX-License-Identifier: AGPL-3.0-or-later
import { beforeEach, describe, expect, it, vi } from "vitest";

type Listener = (event: { payload: unknown }) => void;
const listeners = new Map<string, Listener[]>();
const invoke = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args: unknown[]) => invoke(...args) }));
vi.mock("@tauri-apps/api/event", () => ({
  listen: async (name: string, fn: Listener) => {
    listeners.set(name, [...(listeners.get(name) ?? []), fn]);
    return () =>
      listeners.set(
        name,
        (listeners.get(name) ?? []).filter((l) => l !== fn),
      );
  },
}));

const { request, EngineError, NOTIFICATION_EVENT, RpcCode } = await import("./engine");

function emit(name: string, payload: unknown) {
  for (const fn of listeners.get(name) ?? []) fn({ payload });
}

beforeEach(() => {
  invoke.mockReset();
  listeners.clear();
});

describe("request", () => {
  it("sends method, params and a request id, and returns the result", async () => {
    invoke.mockResolvedValue({ engineVersion: "0.1.0" });
    const result = await request("engine/info", {});
    expect(result).toEqual({ engineVersion: "0.1.0" });
    const [command, args] = invoke.mock.calls[0] as [string, Record<string, unknown>];
    expect(command).toBe("engine_request");
    expect(args.method).toBe("engine/info");
    expect(String(args.requestId)).toMatch(/^ui-/);
  });

  it("routes progress only for its own request id", async () => {
    let resolve: (value: unknown) => void = () => {};
    invoke.mockImplementation((command: string) =>
      command === "engine_request"
        ? new Promise((r) => {
            resolve = r;
          })
        : Promise.resolve(),
    );
    const seen: string[] = [];
    const pending = request(
      "cards/generate",
      { source: "x" },
      { onProgress: (p) => seen.push(p.message) },
    );
    await vi.waitFor(() => expect(invoke).toHaveBeenCalled());
    const { requestId } = invoke.mock.calls[0]?.[1] as { requestId: string };
    emit(NOTIFICATION_EVENT, {
      method: "$/progress",
      params: { requestId: "other", message: "nope" },
    });
    emit(NOTIFICATION_EVENT, {
      method: "$/progress",
      params: { requestId, message: "calling_provider" },
    });
    resolve({ cards: [] });
    await pending;
    expect(seen).toEqual(["calling_provider"]);
    expect(listeners.get(NOTIFICATION_EVENT)).toEqual([]); // unsubscribed afterwards
  });

  it("asks the shell to cancel when aborted", async () => {
    let reject: (err: unknown) => void = () => {};
    invoke.mockImplementation((command: string) =>
      command === "engine_request"
        ? new Promise((_, r) => {
            reject = r;
          })
        : Promise.resolve(),
    );
    const controller = new AbortController();
    const pending = request("cards/generate", { source: "x" }, { signal: controller.signal });
    await vi.waitFor(() => expect(invoke).toHaveBeenCalled());
    controller.abort();
    expect(invoke).toHaveBeenCalledWith(
      "engine_cancel",
      expect.objectContaining({ requestId: expect.any(String) }),
    );
    reject({ code: RpcCode.Cancelled, message: "cancelled" });
    await expect(pending).rejects.toMatchObject({ cancelled: true });
  });

  it("turns error objects into EngineError with a reason", async () => {
    invoke.mockRejectedValue({
      code: RpcCode.AppError,
      message: "no key",
      data: { reason: "missing_api_key", provider: "anthropic" },
    });
    const err = await request("providers/test", { providerId: "anthropic" }).catch((e) => e);
    expect(err).toBeInstanceOf(EngineError);
    expect(err.reason).toBe("missing_api_key");
  });
});
