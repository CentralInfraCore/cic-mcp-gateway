"""compile_context() — the FIRST real cic-mcp-gateway context compiler.

Job: session-context-pack-v1-001. Implements (partially — see module
docstring "Scope" below) the contract documented in
output/gateway-session-adapter-contract.md ("Adapter Input/Output
Contract", "Trust Mapping", "Unavailable-Session Behavior") against the
schema in output/gateway-context-envelope.schema.yaml.

Scope of THIS implementation (input.md "Feladat" 2 + "Nem cél"):
  - only the cic-mcp-session source is consulted (cic-mcp-knowledge,
    cic-mcp-shared, cic-mcp-workdir are NOT wired here — out of scope,
    see job input.md "Nem cél" — those fields are always emitted as empty
    arrays / "not_used", which is schema-valid: every content field MAY be
    an empty array).
  - only 2 cic-mcp-session tools are called per the adapter contract's
    documented 3-tool-class model: get_session_status() ALWAYS first (the
    "Unavailable-Session Behavior" gate), then — only if the session
    resolves — get_session_context_pack() (the "session-context-recall"
    row of the "Adapter Input/Output Contract" table). The other content
    tools (get_session_timeline, search_session_context*,
    get_session_source_refs) are NOT called by this first implementation;
    query_intent is therefore narrowed to a fixed
    "session-context-recall" for this version (see report "Findings").
  - the cic-mcp-session MCP server is started as a REAL, independent
    subprocess and talked to via REAL mcp.client.stdio (NOT an in-process
    Python import of session_server.py's tool functions, and NOT a mock)
    — same evidence bar as
    cic-mcp-session/output/session-mcp-venv-fix-report.md.

Source of truth for the launch command this module reuses (NOT
reinvented): cic-mcp-session/.mcp.json.tpl ("cic-session" entry):
    command: {REPO_ROOT}/.venv-host/bin/python
    args:    [{REPO_ROOT}/mcp-server/session_server.py]
    env:     {"PYTHONPATH": "{REPO_ROOT}"}
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# The cic-mcp-session subprocess reads its DB connection params from these
# env vars (session_store/envelope_writer.py:SessionStoreConfig.from_env()).
# StdioServerParameters.env, when set, REPLACES the subprocess environment
# entirely (mcp.client.stdio.get_default_environment() is only used when
# env=None) — so these must be explicitly forwarded, or the subprocess
# silently falls back to from_env()'s own defaults (localhost:5432/postgres)
# instead of the actual test/dev Postgres instance the gateway is using.
_SESSION_STORE_ENV_VARS = (
    "SESSION_STORE_PG_HOST",
    "SESSION_STORE_PG_PORT",
    "SESSION_STORE_PG_DB",
    "SESSION_STORE_PG_USER",
    "SESSION_STORE_PG_PASSWORD",
)

SOURCE_ID_SESSION = "cic-mcp-session"
TRUST_DOMAIN_SESSION_LOCAL = "session_local"
TRUST_SESSION_DERIVED = "session_derived"


@dataclass(frozen=True)
class SessionServerLaunchConfig:
    """Where/how to start the cic-mcp-session MCP server as a subprocess.

    Mirrors cic-mcp-session/.mcp.json.tpl's "cic-session" entry exactly —
    this dataclass does NOT invent a new launch convention, it is the
    Python-side equivalent of that template's command/args/env.
    """

    repo_root: Path
    python_executable: Path | None = None

    def to_stdio_params(self) -> StdioServerParameters:
        # IMPORTANT: do NOT call Path.resolve()/realpath() on python_exe —
        # .venv-host/bin/python is a symlink to the system interpreter
        # (standard venv layout); resolving it collapses the path to the
        # bare system python3, which lacks the venv's installed packages
        # (psycopg, mcp, ...) and makes the subprocess fail at import time.
        # Only the REPO ROOT is normalized to an absolute path (harmless,
        # not a symlink-follow-through-a-venv case).
        repo_root_abs = self.repo_root.absolute()
        python_exe = self.python_executable or (repo_root_abs / ".venv-host" / "bin" / "python")
        server_script = repo_root_abs / "mcp-server" / "session_server.py"
        env = {"PYTHONPATH": str(repo_root_abs)}
        for var in _SESSION_STORE_ENV_VARS:
            value = os.environ.get(var)
            if value is not None:
                env[var] = value
        return StdioServerParameters(
            command=str(python_exe),
            args=[str(server_script)],
            env=env,
        )


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status_summary_note(status: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Translate a non-empty get_session_status() dict into ONE
    session_derived_notes[] entry, per gateway-session-adapter-contract.md
    "Adapter Input/Output Contract" #1 ("Fordítás": status/started_at/
    last_seen_at/pending_jobs -> one summary session_derived_notes[] entry).
    """
    content = (
        f"Session {session_id} status={status.get('status')!r}, "
        f"started_at={status.get('started_at')!s}, "
        f"last_seen_at={status.get('last_seen_at')!s}, "
        f"pending_jobs={status.get('pending_jobs')!s}."
    )
    return {
        "content": content,
        "trust": TRUST_SESSION_DERIVED,  # aggregated status summary, see contract "Trust Mapping" table
        "ref": f"session:{session_id}:status",
    }


def _context_pack_note(row: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Translate ONE get_session_context_pack() {chunk_id, turn_seq, text}
    row into ONE session_derived_notes[] entry, per
    gateway-session-adapter-contract.md "Adapter Input/Output Contract"
    "session-context-recall" row.
    """
    return {
        "content": row["text"],
        "trust": TRUST_SESSION_DERIVED,  # context_pack = aggregated view, see contract "Trust Mapping" table
        "ref": f"session:{session_id}:chunk:{row['chunk_id']}",
    }


def _empty_per_category(overrides: dict[str, str] | None = None) -> dict[str, str]:
    base = {
        "canonical_facts": "not_used",
        "workdir_facts": "not_used",
        "session_derived_notes": "not_used",
        "shared_memory_notes": "not_used",
    }
    if overrides:
        base.update(overrides)
    return base


async def _compile_context_async(
    session_id: str,
    launch_config: SessionServerLaunchConfig,
    max_chunks: int = 50,
) -> dict[str, Any]:
    """Async implementation — does the REAL subprocess + stdio handshake.

    Synchronous callers should use compile_context() below, which wraps
    this with asyncio.run().
    """
    server_params = launch_config.to_stdio_params()

    sources_used: list[dict[str, Any]] = []
    session_derived_notes: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    proof_requirements: list[dict[str, Any]] = []

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # --- Adapter contract step 1: get_session_status() ALWAYS FIRST ---
            # (gateway-session-adapter-contract.md "Adapter Input/Output
            # Contract" #1 + "Unavailable-Session Behavior" #1: this MUST
            # run before any content tool, so a missing session is caught
            # before a content tool call could produce a silently-empty-
            # but-"successful"-looking envelope.)
            status_result = await session.call_tool(
                "get_session_status", {"session_id": session_id}
            )
            status_dict = _extract_tool_dict(status_result)

            # cic-mcp-session WAS queried regardless of outcome — record it
            # even on a negative ("session not found") answer, per
            # "Unavailable-Session Behavior" #2.
            sources_used.append(
                {
                    "source_id": SOURCE_ID_SESSION,
                    "trust_domain": TRUST_DOMAIN_SESSION_LOCAL,
                    "query_capability_used": "status",
                }
            )

            if not status_dict:
                # --- Unavailable-Session Behavior (contract steps 1-5) ---
                proof_requirements.append(
                    {
                        "description": (
                            f"A kert session_id ({session_id}) nem feloldhato a "
                            "cic-mcp-session retegben - get_session_status() ures "
                            "eredmenyt adott, tehat a session_core.sessions tablaban "
                            "nincs ehhez az ID-hez tartozo sor (vagy torolve lett, "
                            "vagy soha nem letezett, vagy elgepelt ID). A session-"
                            "scope-u tartalom emiatt nem kompilalhato, amig ez nem "
                            "tisztazodik."
                        ),
                        "blocking_for": [f"scope.session_id:{session_id}"],
                    }
                )
                return _build_envelope(
                    session_id=session_id,
                    answer_type="status_summary",
                    sources_used=sources_used,
                    session_derived_notes=[],
                    refs=[],
                    proof_requirements=proof_requirements,
                    per_category_overrides={"session_derived_notes": "unverified"},
                )

            # Session exists -> fold the status dict itself into one note.
            session_derived_notes.append(_status_summary_note(status_dict, session_id))
            refs.append(
                {
                    "ref_id": f"session:{session_id}:status",
                    "source_id": SOURCE_ID_SESSION,
                    "excerpt": str(status_dict),
                }
            )

            # --- Adapter contract step 2: content tool, query_intent =
            # "session-context-recall" -> get_session_context_pack() ---
            pack_result = await session.call_tool(
                "get_session_context_pack",
                {"session_id": session_id, "max_chunks": max_chunks},
            )
            pack_rows = _extract_tool_list(pack_result)

            sources_used.append(
                {
                    "source_id": SOURCE_ID_SESSION,
                    "trust_domain": TRUST_DOMAIN_SESSION_LOCAL,
                    "query_capability_used": "context_pack",
                }
            )

            for row in pack_rows:
                session_derived_notes.append(_context_pack_note(row, session_id))
                refs.append(
                    {
                        "ref_id": f"session:{session_id}:chunk:{row['chunk_id']}",
                        "source_id": SOURCE_ID_SESSION,
                        "excerpt": row["text"][:200],
                    }
                )

            per_category = "medium" if session_derived_notes else "not_used"
            return _build_envelope(
                session_id=session_id,
                answer_type="history_recall" if pack_rows else "status_summary",
                sources_used=sources_used,
                session_derived_notes=session_derived_notes,
                refs=refs,
                proof_requirements=[],
                per_category_overrides={"session_derived_notes": per_category},
            )


def _decode_tool_result(call_tool_result: Any) -> Any:
    """Decode a CallToolResult into its underlying Python value.

    Empirically (verified against the ACTUAL running cic-mcp-session
    server, mcp SDK 1.28.0), FastMCP's stdio transport for THIS server
    does not populate .structuredContent for these tools — it serializes
    the tool's Python return value (list[dict] or dict) as a single JSON
    TextContent block in .content[0].text. This function decodes that;
    .structuredContent is also checked first in case a future SDK/server
    version populates it (forward-compatible, not required by current
    evidence).
    """
    import json

    structured = getattr(call_tool_result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    content = getattr(call_tool_result, "content", None) or []
    if content and getattr(content[0], "text", None) is not None:
        return json.loads(content[0].text)
    return None


def _extract_tool_dict(call_tool_result: Any) -> dict[str, Any]:
    """get_session_status() returns a dict (or {} per
    session_server.py:383-384) — decode the wire result and assert dict
    shape (empty dict is a valid, expected "session not found" value).
    """
    decoded = _decode_tool_result(call_tool_result)
    return decoded if isinstance(decoded, dict) else {}


def _extract_tool_list(call_tool_result: Any) -> list[dict[str, Any]]:
    """get_session_context_pack() (and the other list[dict]-returning
    tools) — decode the wire result and assert list shape.
    """
    decoded = _decode_tool_result(call_tool_result)
    return decoded if isinstance(decoded, list) else []


def _build_envelope(
    *,
    session_id: str,
    answer_type: str,
    sources_used: list[dict[str, Any]],
    session_derived_notes: list[dict[str, Any]],
    refs: list[dict[str, Any]],
    proof_requirements: list[dict[str, Any]],
    per_category_overrides: dict[str, str],
) -> dict[str, Any]:
    """Assemble a full GatewayContextEnvelope dict, schema-valid against
    output/gateway-context-envelope.schema.yaml (all 16 required top-level
    fields present; canonical_facts/workdir_facts/shared_memory_notes/
    conflicts are always [] in this implementation, per "Nem cél" — only
    the cic-mcp-session source is wired).
    """
    overall = "unverified" if per_category_overrides.get("session_derived_notes") == "unverified" else (
        "medium" if session_derived_notes else "unverified"
    )
    return {
        "apiVersion": "cic.gateway/v1",
        "kind": "GatewayContextEnvelope",
        "envelope_id": str(uuid.uuid4()),
        "created_at": _now_rfc3339(),
        "query_intent": "session-context-recall",
        "scope": {"scope_kind": "session", "session_id": session_id},
        "answer_type": answer_type,
        "sources_used": sources_used,
        "trust_summary": {
            "overall_confidence": overall,
            "per_category": _empty_per_category(per_category_overrides),
        },
        "canonical_facts": [],
        "workdir_facts": [],
        "session_derived_notes": session_derived_notes,
        "shared_memory_notes": [],
        "conflicts": [],
        "proof_requirements": proof_requirements,
        "refs": refs,
    }


def compile_context(
    session_id: str,
    repo_root: Path | str,
    max_chunks: int = 50,
    python_executable: Path | str | None = None,
) -> dict[str, Any]:
    """Public, synchronous entry point.

    Args:
        session_id: the cic-mcp-session session_core.sessions.session_id
            to compile a GatewayContextEnvelope for (scope.scope_kind =
            "session").
        repo_root: path to a cic-mcp-session checkout — used to locate
            .venv-host/bin/python and mcp-server/session_server.py, exactly
            mirroring cic-mcp-session/.mcp.json.tpl's "cic-session" entry.
        max_chunks: passed through to get_session_context_pack() (default
            mirrors the tool's own default, mcp-server/session_server.py:303).
        python_executable: override for the interpreter used to launch the
            session server subprocess (defaults to
            {repo_root}/.venv-host/bin/python).

    Returns:
        dict: a GatewayContextEnvelope, schema-valid against
        output/gateway-context-envelope.schema.yaml.
    """
    import asyncio

    launch_config = SessionServerLaunchConfig(
        repo_root=Path(repo_root),
        python_executable=Path(python_executable) if python_executable else None,
    )
    return asyncio.run(
        _compile_context_async(session_id, launch_config, max_chunks=max_chunks)
    )
