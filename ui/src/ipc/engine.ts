// SPDX-License-Identifier: AGPL-3.0-or-later
// Typed client for the Python engine (roadmap A07). Requests go through the Rust shell,
// which forwards them over stdio; progress comes back as Tauri events.
import { invoke } from "@tauri-apps/api/core";
import { type UnlistenFn, listen } from "@tauri-apps/api/event";
import type { Method, MethodMap, ProgressParams } from "./protocol.gen";

export const NOTIFICATION_EVENT = "engine://notification";
export const STATUS_EVENT = "engine://status";

export type EngineStatus =
  | { state: "starting" }
  | { state: "ready"; engineVersion: string; protocolVersion: number }
  | { state: "restarting"; attempt: number; reason: string }
  | { state: "failed"; reason: string };

export interface RpcErrorShape {
  code: number;
  message: string;
  data?: { reason?: string; [key: string]: unknown };
}

/** JSON-RPC error codes the UI cares about. Mirrors engine/src/sfcm_engine/errors.py. */
export const RpcCode = {
  InvalidParams: -32602,
  Cancelled: -32800,
  AppError: -32000,
  EngineUnavailable: -32099, // raised by the shell, not the engine
} as const;

export class EngineError extends Error {
  readonly code: number;
  /** Stable, translatable reason such as "missing_api_key" (APP_ERROR only). */
  readonly reason: string | undefined;
  readonly data: RpcErrorShape["data"];

  constructor(shape: RpcErrorShape) {
    super(shape.message);
    this.name = "EngineError";
    this.code = shape.code;
    this.reason = shape.data?.reason;
    this.data = shape.data;
  }

  get cancelled(): boolean {
    return this.code === RpcCode.Cancelled;
  }
}

function toEngineError(err: unknown): EngineError {
  if (err instanceof EngineError) return err;
  if (err && typeof err === "object" && "code" in err && "message" in err) {
    return new EngineError(err as RpcErrorShape);
  }
  return new EngineError({ code: RpcCode.EngineUnavailable, message: String(err) });
}

export interface RequestOptions {
  onProgress?: (progress: ProgressParams) => void;
  signal?: AbortSignal;
}

let counter = 0;
function newRequestId(): string {
  counter += 1;
  const random = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
  return `ui-${counter}-${random}`;
}

export async function request<M extends Method>(
  method: M,
  params: MethodMap[M]["params"],
  options: RequestOptions = {},
): Promise<MethodMap[M]["result"]> {
  const { onProgress, signal } = options;
  if (signal?.aborted) {
    throw new EngineError({ code: RpcCode.Cancelled, message: "cancelled" });
  }
  const requestId = newRequestId();
  let unlisten: UnlistenFn | undefined;
  if (onProgress) {
    unlisten = await listen<{ method: string; params: ProgressParams }>(
      NOTIFICATION_EVENT,
      (event) => {
        const { method: name, params: progress } = event.payload;
        if (name === "$/progress" && progress.requestId === requestId) onProgress(progress);
      },
    );
  }
  const onAbort = () => {
    void invoke("engine_cancel", { requestId });
  };
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    return await invoke<MethodMap[M]["result"]>("engine_request", { method, params, requestId });
  } catch (err) {
    throw toEngineError(err);
  } finally {
    signal?.removeEventListener("abort", onAbort);
    unlisten?.();
  }
}

export function getStatus(): Promise<EngineStatus> {
  return invoke<EngineStatus>("engine_status");
}

export function onStatus(handler: (status: EngineStatus) => void): Promise<UnlistenFn> {
  return listen<EngineStatus>(STATUS_EVENT, (event) => handler(event.payload));
}
