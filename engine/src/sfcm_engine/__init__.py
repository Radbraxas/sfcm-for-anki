# SPDX-License-Identifier: AGPL-3.0-or-later
"""SFCM for Anki engine: the Python half of the app (see docs/adr/0001-architecture.md)."""

__version__ = "0.1.0"  # x-release-please-version

# Bump on any breaking change to engine/schema/protocol.schema.json.
# The Rust shell refuses to talk to an engine with a different value.
PROTOCOL_VERSION = 1
