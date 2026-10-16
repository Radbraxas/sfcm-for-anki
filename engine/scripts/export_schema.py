# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the protocol as one JSON Schema document (roadmap A07).

Usage: python engine/scripts/export_schema.py engine/schema/protocol.schema.json

`$defs` holds every params/result model. The `x-methods`, `x-shell-methods` and
`x-notifications` maps say which models belong to which message; the UI type
generator reads them to build a typed method map.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, models_json_schema

from sfcm_engine import PROTOCOL_VERSION
from sfcm_engine.protocol import METHODS, NOTIFICATIONS, SHELL_METHODS


def build() -> dict[str, Any]:
    # What the engine receives is described as input (fields with defaults are
    # optional); what it sends is described as output (every field present).
    inputs = [p for p, _ in METHODS.values()] + [r for _, r in SHELL_METHODS.values()]
    outputs = [r for _, r in METHODS.values()] + [p for p, _ in SHELL_METHODS.values()]
    outputs += list(NOTIFICATIONS.values())
    pairs: list[tuple[type[BaseModel], JsonSchemaMode]] = [
        *((m, "validation") for m in dict.fromkeys(inputs)),
        *((m, "serialization") for m in dict.fromkeys(outputs)),
    ]
    _, schema = models_json_schema(
        pairs,
        by_alias=True,
        ref_template="#/$defs/{model}",
    )

    def pair(table: dict[str, tuple[type[BaseModel], type[BaseModel]]]) -> dict[str, Any]:
        return {
            name: {"params": params.__name__, "result": result.__name__}
            for name, (params, result) in sorted(table.items())
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "SFCM engine protocol",
        "x-protocol-version": PROTOCOL_VERSION,
        "x-methods": pair(METHODS),
        "x-shell-methods": pair(SHELL_METHODS),
        "x-notifications": {k: v.__name__ for k, v in sorted(NOTIFICATIONS.items())},
        "$defs": dict(sorted(schema.get("$defs", {}).items())),
    }


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    text = json.dumps(build(), indent=2, sort_keys=False) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
