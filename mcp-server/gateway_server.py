#!/usr/bin/env python3
"""
Gateway MCP server for cic-mcp-gateway — the FIRST gateway-specific MCP
server in this repo.

Job: gateway-context-pack-production-wiring-001. Before this job,
gateway_core.compile_context.compile_context() (job session-context-pack-
v1-001, hardened by gateway-compile-context-test-hardening-001) had ZERO
production callers — only its own module and
tests/test_gateway_core/test_compile_context.py invoked it. This module is
the first actual "production call site": it exposes compile_context() to
an MCP client as a tool.

IMPORTANT — distinct from mcp-server/server.py: that module is the
inherited, generic cic-graph KB-graph server (token search, node lookup,
focus_pack, etc.) — a totally unrelated concept that builds its index from
kb_data/pkl artifacts (base-repo template heritage, see CLAUDE.md "Jelenlegi
állapot"). This module is NOT a modification of that file and does NOT
import from it. This module exposes gateway_core.compile_context.
compile_context() to an MCP client, via a single FastMCP instance named
"cic-gateway" (not "cic-graph") — same separation pattern as
cic-mcp-session/mcp-server/session_server.py's own "cic-session" instance
vs. that repo's inherited mcp-server/server.py.

Source of truth for the function this module calls (NOT reimplemented
here — see "Nem cél" in input.md, compile_context() itself is not
modified): gateway_core/compile_context.py:354 compile_context(session_id,
repo_root, max_chunks=50, python_executable=None) -> dict[str, Any].
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import asyncio
from functools import partial

from mcp.server.fastmcp import FastMCP

# gateway_core is this repo's own package (see gateway_core/__init__.py) —
# make it importable when this script is launched directly as a subprocess
# (mirrors cic-mcp-session/mcp-server/session_server.py's own sys.path
# handling for session_store).
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway_core.compile_context import compile_context  # noqa: E402

mcp = FastMCP("cic-gateway")


@mcp.tool()
async def get_gateway_context_pack(
    session_id: str, session_repo_root: str, max_chunks: int = 50
) -> dict[str, Any]:
    """Compile a GatewayContextEnvelope for one session, by calling the
    EXISTING, already-tested gateway_core.compile_context.compile_context()
    (job session-context-pack-v1-001, hardened by
    gateway-compile-context-test-hardening-001) — this tool does NOT
    reimplement any of compile_context()'s logic; it only:
      1. forwards (session_id, repo_root=session_repo_root, max_chunks) to
         compile_context(), which itself starts the cic-mcp-session MCP
         server as a real subprocess and talks to it via real
         mcp.client.stdio (see gateway_core/compile_context.py module
         docstring),
      2. returns the resulting GatewayContextEnvelope dict unchanged.

    compile_context() is a SYNCHRONOUS function that internally calls
    asyncio.run() (gateway_core/compile_context.py:385) to drive its own
    async subprocess/stdio logic. FastMCP's stdio transport already runs
    this tool inside a live asyncio event loop (mcp/server/fastmcp/
    server.py), so calling compile_context() directly here would hit
    "asyncio.run() cannot be called from a running event loop" — this is
    NOT a defect of compile_context() itself (its own direct-call test,
    tests/test_gateway_core/test_compile_context.py, runs it from
    synchronous pytest code with no event loop yet running). The fix is on
    this (caller) side: run the synchronous compile_context() in a worker
    thread via loop.run_in_executor(), so this coroutine awaits a thread
    that is free to start its OWN event loop with asyncio.run() — no
    asyncio internals of compile_context() are touched or reimplemented.

    Args:
        session_id: the cic-mcp-session session_core.sessions.session_id to
            compile a GatewayContextEnvelope for.
        session_repo_root: path to a cic-mcp-session checkout — used by
            compile_context() to locate .venv-host/bin/python and
            mcp-server/session_server.py (mirrors cic-mcp-session/
            .mcp.json.tpl's "cic-session" entry).
        max_chunks: passed through to compile_context()'s own max_chunks
            parameter (default mirrors compile_context()'s own default).

    Returns:
        dict: a GatewayContextEnvelope, schema-valid against
        output/gateway-context-envelope.schema.yaml.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(
            compile_context,
            session_id=session_id,
            repo_root=session_repo_root,
            max_chunks=max_chunks,
        ),
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
