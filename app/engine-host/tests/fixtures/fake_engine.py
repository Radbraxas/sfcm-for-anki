# SPDX-License-Identifier: AGPL-3.0-or-later
"""A tiny stand-in for the real engine, for testing the Rust supervisor.

FAKE_MODE=normal (default) | bad_protocol
Methods: echo, slow (answers only when cancelled), ask_secret, crash.
"""

import json
import os
import sys


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


protocol = 999 if os.environ.get("FAKE_MODE") == "bad_protocol" else 1
send(
    {
        "jsonrpc": "2.0",
        "method": "$/ready",
        "params": {"engineVersion": "fake", "protocolVersion": protocol},
    }
)

slow = set()
waiting_for_secret = {}

for line in sys.stdin:
    msg = json.loads(line)
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method is None and msg_id in waiting_for_secret:
        original = waiting_for_secret.pop(msg_id)
        send({"jsonrpc": "2.0", "id": original, "result": msg.get("result")})
    elif method == "echo":
        send(
            {
                "jsonrpc": "2.0",
                "method": "$/progress",
                "params": {"requestId": msg_id, "message": "echoing"},
            }
        )
        send({"jsonrpc": "2.0", "id": msg_id, "result": params})
    elif method == "slow":
        slow.add(msg_id)
    elif method == "$/cancelRequest" and params.get("id") in slow:
        slow.discard(params["id"])
        send(
            {
                "jsonrpc": "2.0",
                "id": params["id"],
                "error": {"code": -32800, "message": "cancelled"},
            }
        )
    elif method == "ask_secret":
        waiting_for_secret["e1"] = msg_id
        send(
            {
                "jsonrpc": "2.0",
                "id": "e1",
                "method": "secrets/get",
                "params": {"service": "anthropic"},
            }
        )
    elif method == "crash":
        sys.exit(3)
