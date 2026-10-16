// SPDX-License-Identifier: AGPL-3.0-or-later
//! API keys in the OS keychain (roadmap A08): macOS Keychain, Windows Credential
//! Manager, Secret Service on Linux. Only the services below can be read or written.

use serde_json::{json, Value};
use sfcm_engine_host::{RpcError, ShellHandler};

/// Keychain "service" name; each provider is an account under it.
pub const KEYCHAIN_SERVICE: &str = "org.sfcmforanki.desktop";
pub const ALLOWED: [&str; 3] = ["anthropic", "openai", "custom"];

fn entry(account: &str) -> Result<keyring::Entry, String> {
    if !ALLOWED.contains(&account) {
        return Err(format!("{account} is not a known API key"));
    }
    keyring::Entry::new(KEYCHAIN_SERVICE, account).map_err(|e| e.to_string())
}

pub fn get(account: &str) -> Result<Option<String>, String> {
    match entry(account)?.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(err) => Err(err.to_string()),
    }
}

pub fn set(account: &str, value: &str) -> Result<(), String> {
    let value = value.trim();
    if value.is_empty() {
        return Err("the key is empty".into());
    }
    entry(account)?
        .set_password(value)
        .map_err(|e| e.to_string())
}

pub fn delete(account: &str) -> Result<(), String> {
    match entry(account)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(err.to_string()),
    }
}

/// Answers the engine's `secrets/get` requests.
pub struct KeychainShell;

impl ShellHandler for KeychainShell {
    fn handle(&self, method: &str, params: &Value) -> Result<Value, RpcError> {
        if method != "secrets/get" {
            return Err(RpcError::new(
                -32601,
                format!("unknown shell method {method}"),
            ));
        }
        let service = params.get("service").and_then(Value::as_str).unwrap_or("");
        if !ALLOWED.contains(&service) {
            // Local providers have no key; answer "none" rather than an error.
            return Ok(json!({"value": null}));
        }
        get(service)
            .map(|value| json!({"value": value}))
            .map_err(|e| RpcError::new(-32000, e))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn use_mock_keychain() {
        keyring::set_default_credential_builder(keyring::mock::default_credential_builder());
    }

    #[test]
    fn unknown_accounts_are_refused() {
        assert!(entry("../../etc").is_err());
        assert!(set("github", "token").is_err());
    }

    #[test]
    fn cloud_and_custom_accounts_are_allowed() {
        for account in ["anthropic", "openai", "custom"] {
            assert!(entry(account).is_ok(), "{account} should be allowed");
        }
        assert!(entry("ollama").is_err());
    }

    #[test]
    fn local_providers_get_no_key() {
        let reply = KeychainShell
            .handle("secrets/get", &json!({"service": "ollama"}))
            .unwrap();
        assert_eq!(reply, json!({"value": null}));
    }

    #[test]
    fn unknown_methods_are_rejected() {
        let err = KeychainShell.handle("fs/read", &json!({})).unwrap_err();
        assert_eq!(err.code, -32601);
    }

    #[test]
    fn empty_keys_are_rejected() {
        use_mock_keychain();
        assert!(set("anthropic", "   ").is_err());
    }
}
