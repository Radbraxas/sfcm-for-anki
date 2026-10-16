# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine entry point. The Rust shell starts this and talks to it over stdio.

Environment:
  SFCM_DATA_DIR     where the database lives (the shell passes the OS app-data dir)
  SFCM_PROMPTS_DIR  prompt templates (defaults to the bundled or repo copy)
  SFCM_LOG          log level for stderr, default INFO
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from . import PROTOCOL_VERSION, __version__
from .app import App
from .db import Database
from .llm.registry import ProviderRegistry
from .prompts import PromptLibrary
from .protocol import ReadyParams, dump
from .redaction import configure_logging
from .rpc import Server, serve_stdio, stdout_sender


def default_data_dir() -> Path:
    return Path(os.environ.get("SFCM_DATA_DIR") or Path.cwd() / ".sfcm-data")


async def run_stdio(data_dir: Path) -> None:
    db = Database(data_dir / "sfcm.sqlite3")
    db.migrate()
    server = Server(send=stdout_sender(sys.stdout.buffer))
    App(db=db, data_dir=data_dir, prompts=PromptLibrary(), registry=ProviderRegistry(db)).register(
        server
    )
    server.notify(
        "$/ready", dump(ReadyParams(engine_version=__version__, protocol_version=PROTOCOL_VERSION))
    )
    try:
        await serve_stdio(server)
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfcm-engine")
    parser.add_argument("--version", action="store_true", help="print versions and exit")
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.version:
        print(f"sfcm-engine {__version__} (protocol {PROTOCOL_VERSION})")
        return 0
    configure_logging(os.environ.get("SFCM_LOG", "INFO"))
    asyncio.run(run_stdio(args.data_dir or default_data_dir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
