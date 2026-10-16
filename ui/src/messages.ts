// SPDX-License-Identifier: AGPL-3.0-or-later
// English text for engine reasons and progress keys. Moves to i18next in roadmap A14.
import { EngineError, RpcCode } from "./ipc/engine";

const REASONS: Record<string, string> = {
  missing_api_key: "Add an API key for this provider first.",
  provider_auth: "The provider rejected the API key. Check it and save it again.",
  provider_rate_limited: "The provider is rate limiting requests. Wait a minute and try again.",
  provider_unavailable:
    "Couldn't reach the provider. Check your connection, or that the local server is running.",
  provider_bad_request: "The provider rejected the request.",
  model_not_found: "That model isn't available for this provider. Pick another model.",
  local_only_blocked:
    "Local-only mode is on, so cloud providers are blocked. Choose Ollama or LM Studio, or turn local-only off.",
  provider_not_configured: "Set a base URL and a model for the custom provider first.",
  invalid_output: "The model's reply couldn't be read as cards. Try again or ask for fewer cards.",
  output_truncated: "The reply was cut off. Ask for fewer cards at a time.",
  refused: "The model declined this material. Try different source text.",
  invalid_export_path: "Choose a folder that exists and a file name ending in .apkg.",
  shell_unavailable: "The app couldn't reach your system keychain.",
};

const PROGRESS: Record<string, string> = {
  preparing_prompt: "Preparing…",
  calling_provider: "Writing cards…",
  validating: "Checking cards…",
  writing_package: "Writing the Anki package…",
  done: "Done.",
};

export function describeError(err: unknown): string {
  if (err instanceof EngineError) {
    if (err.reason && REASONS[err.reason]) return REASONS[err.reason] as string;
    if (err.code === RpcCode.EngineUnavailable)
      return "The engine isn't running. It restarts automatically.";
    return err.message;
  }
  return String(err);
}

export function describeProgress(key: string): string {
  return PROGRESS[key] ?? key;
}
