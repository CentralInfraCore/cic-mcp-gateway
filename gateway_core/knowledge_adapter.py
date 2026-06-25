"""knowledge_adapter — the cic-mcp-knowledge source adapter for the gateway.

Job: gateway-knowledge-shared-adapters-001. This is the SECOND real source
wired into compile_context() (the first was cic-mcp-session, see
compile_context.py). It consults cic-mcp-knowledge — the "reviewed and
promoted canonical knowledge" layer — and produces canonical_facts[]
entries for the GatewayContextEnvelope.

Trust contract (output/gateway-context-envelope.schema.yaml, canonical_facts
description): content from cic-mcp-knowledge — and ONLY from there — may go
into canonical_facts[]. canonical_facts items DELIBERATELY carry NO `trust`
field: placement in canonical_facts IS the canonical marking. The gateway
never upgrades or invents this status — it is earned upstream by
cic-mcp-knowledge's own review/promotion flow.

Launch contract (NOT reinvented here): cic-mcp-knowledge/.mcp.json.tpl's
"cic-graph" entry —
    command: {REPO_ROOT}/p_venv/bin/python
    args:    [{REPO_ROOT}/mcp-server/server.py]
    env:     {"KB_DATA_DIR": "{REPO_ROOT}/kb_data/pkl"}
This dataclass is the Python-side equivalent of that template. The server is
started as a REAL, independent subprocess and talked to via REAL
mcp.client.stdio (same evidence bar as the session adapter — NOT an
in-process import of server.py, NOT a mock).

Query contract: search_query(query, top_k) returns ranked hits
{chunk_id, score, matched_tokens, file_paths, line_range} — note NO text
(server.py:search_query deliberately omits chunk bodies). The adapter then
calls get_chunk(chunk_id) per hit to retrieve the actual content, which is
what becomes the canonical_fact's `content`. cic-mcp-knowledge is a
READ-ONLY dependency for this job — this module only calls its tools, it
never writes to or modifies that repo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SOURCE_ID_KNOWLEDGE = "cic-mcp-knowledge"
TRUST_DOMAIN_KNOWLEDGE_CANONICAL = "knowledge_canonical"


@dataclass(frozen=True)
class KnowledgeServerLaunchConfig:
    """Where/how to start the cic-mcp-knowledge MCP server as a subprocess.

    Mirrors cic-mcp-knowledge/.mcp.json.tpl's "cic-graph" entry exactly —
    this dataclass does NOT invent a new launch convention.
    """

    repo_root: Path
    python_executable: Path | None = None
    kb_data_dir: Path | None = None

    def to_stdio_params(self) -> StdioServerParameters:
        # IMPORTANT: do NOT call Path.resolve()/realpath() on python_exe —
        # p_venv/bin/python is a symlink to the system interpreter (standard
        # venv layout); resolving it collapses to the bare system python3,
        # which lacks the venv's installed packages (faiss, mcp,
        # sentence_transformers, ...) and makes the subprocess fail at import
        # time. Only the REPO ROOT is normalized to an absolute path.
        repo_root_abs = self.repo_root.absolute()
        python_exe = self.python_executable or (
            repo_root_abs / "p_venv" / "bin" / "python"
        )
        server_script = repo_root_abs / "mcp-server" / "server.py"
        kb_dir = self.kb_data_dir or (repo_root_abs / "kb_data" / "pkl")
        # StdioServerParameters.env, when set, REPLACES the subprocess
        # environment entirely — so the server's KB_DATA_DIR (and a
        # PYTHONPATH that lets it import its own modules) must be forwarded
        # explicitly, or the server silently falls back to its in-repo
        # kb_data/pkl default.
        env = {
            "PYTHONPATH": str(repo_root_abs),
            "KB_DATA_DIR": str(kb_dir),
        }
        return StdioServerParameters(
            command=str(python_exe),
            args=[str(server_script)],
            env=env,
        )


def _decode_tool_result(call_tool_result: Any) -> Any:
    """Decode a CallToolResult into its underlying Python value.

    Duplicated (intentionally, to keep knowledge_adapter importable without
    pulling in compile_context) from compile_context._decode_tool_result —
    same logic: .structuredContent first (unwrapping the mcp SDK's
    {"result": ...} envelope), else the JSON-encoded .content[0].text block
    FastMCP's stdio transport emits for these tools.
    """
    structured = getattr(call_tool_result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    content = getattr(call_tool_result, "content", None) or []
    if content and getattr(content[0], "text", None) is not None:
        return json.loads(content[0].text)
    return None


def _extract_chunk_content(chunk: Any) -> str:
    """cic-mcp-knowledge get_chunk() returns a dict whose body lives under
    "content" (or legacy "text"), mirroring server.py:_extract_chunk_text.
    Returns "" if neither is present (caller skips empty facts).
    """
    if not isinstance(chunk, dict):
        return ""
    value = chunk.get("content")
    if not value:
        value = chunk.get("text")
    return str(value) if value else ""


async def search_knowledge(
    launch_config: KnowledgeServerLaunchConfig,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Query the cic-mcp-knowledge MCP server over REAL stdio and return
    canonical_fact-shaped items.

    Each returned dict has the shape compile_context() folds into the
    envelope's canonical_facts[] / refs[]:
        {
          "content": <chunk body, from get_chunk()>,
          "ref": "knowledge:chunk:<chunk_id>",
          "chunk_id": <chunk_id>,        # kept for refs[] excerpt building
          "score": <search_query score>,
          "file_paths": [<paths>],
        }
    NOTE: NO "trust" key — canonical_facts placement is the canonical
    marking (schema: canonical_facts items have no trust field).

    Steps (per the query contract in the module docstring):
      1. search_query(query, top_k) -> ranked hits (no body).
      2. get_chunk(chunk_id) per hit -> the actual content.
    Hits whose chunk body is empty are skipped (a hit with no retrievable
    content is not a usable canonical fact).
    """
    server_params = launch_config.to_stdio_params()
    facts: list[dict[str, Any]] = []

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            search_result = await session.call_tool(
                "search_query", {"query": query, "top_k": top_k}
            )
            hits = _decode_tool_result(search_result)
            if not isinstance(hits, list):
                return []

            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                chunk_id = hit.get("chunk_id")
                if not chunk_id:
                    continue
                chunk_result = await session.call_tool(
                    "get_chunk", {"chunk_id": chunk_id}
                )
                content = _extract_chunk_content(_decode_tool_result(chunk_result))
                if not content:
                    continue
                facts.append(
                    {
                        "content": content,
                        "ref": f"knowledge:chunk:{chunk_id}",
                        "chunk_id": chunk_id,
                        "score": hit.get("score"),
                        "file_paths": hit.get("file_paths") or [],
                    }
                )

    return facts
