// SPDX-License-Identifier: AGPL-3.0-or-later
//! Starts the Python engine, keeps it running, and routes JSON-RPC messages to and
//! from it (roadmap A06, A07).
//!
//! The protocol is newline-delimited JSON-RPC 2.0 over the child's stdin/stdout.
//! This crate never interprets request payloads: it matches responses to requests,
//! forwards notifications, and answers the few requests the engine makes to the
//! shell (such as `secrets/get`) through a [`ShellHandler`].
//!
//! It has no Tauri dependency so it can be tested without a webview.

mod messages;
mod supervisor;

pub use messages::{Incoming, RpcError};
pub use supervisor::{backoff, EngineConfig, EngineHost, EngineStatus, EventSink, ShellHandler};

/// Protocol version this shell speaks. Must match `PROTOCOL_VERSION` in the engine.
pub const PROTOCOL_VERSION: u64 = 1;

/// Error code used when the engine is not running. Outside the range the engine uses.
pub const ENGINE_UNAVAILABLE: i64 = -32099;
