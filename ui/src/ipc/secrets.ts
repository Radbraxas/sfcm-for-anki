// SPDX-License-Identifier: AGPL-3.0-or-later
// API keys go straight from this screen to the OS keychain through the Rust shell.
// They never pass through the engine and are never stored by the UI (roadmap A08).
import { invoke } from "@tauri-apps/api/core";

export type KeyService = "anthropic" | "openai" | "custom";

export function saveKey(service: KeyService, value: string): Promise<void> {
  return invoke("secrets_set", { service, value });
}

export function deleteKey(service: KeyService): Promise<void> {
  return invoke("secrets_delete", { service });
}

export function hasKey(service: KeyService): Promise<boolean> {
  return invoke<boolean>("secrets_has", { service });
}
