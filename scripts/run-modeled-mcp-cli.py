#!/usr/bin/env python3
"""Run the modeled MCP CLI entrypoint (scaffold hardening only).

This script intentionally stays below the released ceiling (`pageReadyObserved`).
It composes:

- released-scope input resolution (CLI args then env vars)
- MCP stdio constructor config parsing (CLI args only; no new MCP env vars)

It then runs the released-scope mission sequence via MCP adapter injection and
writes a minimal run summary artifact under the run root.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from ez_ax.graph.modeled_mcp_cli_entrypoint import run_modeled_mcp_cli_entrypoint


def _parse_args(argv: list[str]) -> tuple[Path, list[str]]:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--base-dir",
        dest="base_dir",
        default=".",
        help="Base directory for artifacts (default: current directory).",
    )
    parsed, rest = parser.parse_known_args(argv)
    base_dir = Path(parsed.base_dir)
    return base_dir, rest


async def _run() -> int:
    base_dir, passthrough = _parse_args(sys.argv[1:])
    summary = await run_modeled_mcp_cli_entrypoint(
        argv=passthrough,
        env=os.environ,
        base_dir=base_dir,
    )
    print(summary.summary_path)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
