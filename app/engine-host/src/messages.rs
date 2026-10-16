// SPDX-License-Identifier: AGPL-3.0-or-later
//! Classifying lines the engine writes to stdout.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// A JSON-RPC error object, as sent to the UI.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RpcError {
    pub code: i64,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

impl RpcError {
    pub fn new(code: i64, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            data: None,
        }
    }
}

/// One message from the engine.
#[derive(Debug, PartialEq)]
pub enum Incoming {
    /// Reply to a request the shell forwarded.
    Response {
        id: String,
        result: Result<Value, RpcError>,
    },
    /// The engine asking the shell for something.
    Request {
        id: Value,
        method: String,
        params: Value,
    },
    Notification {
        method: String,
        params: Value,
    },
    /// Not valid JSON-RPC. Logged and dropped.
    Invalid(String),
}

fn id_key(id: &Value) -> String {
    match id {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

impl Incoming {
    pub fn parse(line: &str) -> Incoming {
        let value: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(err) => return Incoming::Invalid(format!("bad JSON: {err}")),
        };
        let Value::Object(mut obj) = value else {
            return Incoming::Invalid("not an object".into());
        };
        let id = obj.remove("id").filter(|v| !v.is_null());
        let method = obj
            .remove("method")
            .and_then(|m| m.as_str().map(String::from));
        let params = obj.remove("params").unwrap_or(Value::Null);
        match (id, method) {
            (Some(id), Some(method)) => Incoming::Request { id, method, params },
            (None, Some(method)) => Incoming::Notification { method, params },
            (Some(id), None) => {
                let result = if let Some(err) = obj.remove("error") {
                    Err(serde_json::from_value(err).unwrap_or_else(|e| {
                        RpcError::new(-32603, format!("malformed error object: {e}"))
                    }))
                } else {
                    Ok(obj.remove("result").unwrap_or(Value::Null))
                };
                Incoming::Response {
                    id: id_key(&id),
                    result,
                }
            }
            (None, None) => Incoming::Invalid("neither id nor method".into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn classifies_messages() {
        assert_eq!(
            Incoming::parse(r#"{"jsonrpc":"2.0","id":"ui-1","result":{"ok":true}}"#),
            Incoming::Response {
                id: "ui-1".into(),
                result: Ok(json!({"ok": true}))
            }
        );
        assert_eq!(
            Incoming::parse(
                r#"{"jsonrpc":"2.0","id":7,"error":{"code":-32800,"message":"cancelled"}}"#
            ),
            Incoming::Response {
                id: "7".into(),
                result: Err(RpcError::new(-32800, "cancelled"))
            }
        );
        assert_eq!(
            Incoming::parse(
                r#"{"jsonrpc":"2.0","id":"e1","method":"secrets/get","params":{"service":"anthropic"}}"#
            ),
            Incoming::Request {
                id: json!("e1"),
                method: "secrets/get".into(),
                params: json!({"service": "anthropic"})
            }
        );
        assert_eq!(
            Incoming::parse(
                r#"{"jsonrpc":"2.0","method":"$/progress","params":{"requestId":"ui-1"}}"#
            ),
            Incoming::Notification {
                method: "$/progress".into(),
                params: json!({"requestId": "ui-1"})
            }
        );
        assert!(matches!(Incoming::parse("nope"), Incoming::Invalid(_)));
        assert!(matches!(Incoming::parse("[]"), Incoming::Invalid(_)));
    }

    #[test]
    fn error_data_is_kept_for_the_ui() {
        let msg = r#"{"id":"a","error":{"code":-32000,"message":"no key","data":{"reason":"missing_api_key"}}}"#;
        let Incoming::Response {
            result: Err(err), ..
        } = Incoming::parse(msg)
        else {
            panic!("expected error response");
        };
        assert_eq!(err.data, Some(json!({"reason": "missing_api_key"})));
    }
}
