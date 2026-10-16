# SPDX-License-Identifier: AGPL-3.0-or-later
"""End to end: start the real engine process and talk to it over stdio."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_engine_process_handshake_and_eof(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "sfcm_engine", "--data-dir", str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin and proc.stdout
    ready = json.loads(proc.stdout.readline())
    assert ready["method"] == "$/ready"
    assert ready["params"]["protocolVersion"] == 1
    proc.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"engine/info","params":{}}\n')
    proc.stdin.flush()
    reply = json.loads(proc.stdout.readline())
    assert reply["result"]["dataDir"] == str(tmp_path)
    proc.stdin.close()  # the shell going away must stop the engine
    assert proc.wait(timeout=5) == 0
    assert (tmp_path / "sfcm.sqlite3").exists()
