"""Real, executed multi-source evidence for gateway-knowledge-shared-adapters-001.

Same evidence bar as test_compile_context.py: NO mocks, NO in-process
imports of the source servers' tool functions.

  1. knowledge adapter -> a REAL cic-mcp-knowledge MCP server subprocess
     (started via mcp.client.stdio), queried over a lightweight fixture KB
     that exercises the server's BM25/inverted-index fallback path (no
     faiss index / embedding model artifacts needed — search_query falls
     back to the inverted index, see cic-mcp-knowledge/mcp-server/server.py
     load_kb()).
  2. shared adapter -> a REAL Postgres shared_core.candidates table
     (psycopg, addressed via the SESSION_STORE_PG_* env vars, same
     convention as cic-mcp-shared's own aggregator tests).
  3. the multi-source ENVELOPE assembly (_gather_multi_source +
     _build_envelope) over BOTH real sources, asserting per-element trust
     preservation: knowledge -> canonical_facts[] (NO trust field), shared
     -> shared_memory_notes[] (row.trust verbatim), mixed-trust EXCLUDED.

Requires (fails loudly — never silently skips — same stance as
cic-mcp-session/test_session_api.py):
  - GATEWAY_TEST_KNOWLEDGE_REPO  : a cic-mcp-knowledge checkout.
  - GATEWAY_TEST_KNOWLEDGE_PYTHON: a python interpreter with faiss + mcp +
    sentence_transformers installed (cic-mcp-knowledge/mcp-server/server.py
    imports faiss + sentence_transformers unconditionally at module top, so
    even the BM25 fallback needs them importable). Defaults to
    {repo}/p_venv/bin/python.
  - SESSION_STORE_PG_* (or PG* fallback): a reachable Postgres.

ALL fixture content below is SYNTHETIC — no real session/personal content
in fixtures (same rule as the cross-session aggregator test).
"""

from __future__ import annotations

import asyncio
import os
import pickle
import re
import uuid
from pathlib import Path

import psycopg
import pytest

from gateway_core.compile_context import (
    _build_envelope,
    _gather_multi_source,
    _shared_per_category,
)
from gateway_core.knowledge_adapter import (
    KnowledgeServerLaunchConfig,
    search_knowledge,
)
from gateway_core.shared_adapter import (
    ALLOWED_SHARED_TRUST,
    SharedDbConfig,
    search_shared_candidates,
)

# Synthetic canonical statement — contains the distinctive token the queries
# below search for. NOT real KB content.
_FIXTURE_CHUNK_ID = "fixture-chunk-prooftrace"
_FIXTURE_CONTENT = (
    "ProofTrace is the cryptographically verifiable execution ledger of "
    "CentralInfraCore: every step carries a signed, replayable proof."
)
_FIXTURE_QUERY = "prooftrace"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _tokenize(text: str) -> list[str]:
    # Mirror cic-mcp-knowledge/mcp-server/server.py:_tokenize (lowercase,
    # alpha-only) so the inverted index keys match what search_query looks up.
    return [w for w in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if w.isalpha()]


def _build_fixture_kb(target_dir: Path) -> None:
    """Write the 4 mandatory pkls (chunks/nodes/edges/inverted) for the
    BM25/inverted fallback path — deliberately NO faiss.index / model so the
    server uses its token-search fallback.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    chunk = {
        "id": _FIXTURE_CHUNK_ID,
        "content": _FIXTURE_CONTENT,
        "file_paths": ["fixture/prooftrace.md"],
        "metadata": {},
    }
    with (target_dir / "chunks.pkl").open("wb") as f:
        pickle.dump({"chunks": {_FIXTURE_CHUNK_ID: chunk}}, f)
    with (target_dir / "graph_nodes.pkl").open("wb") as f:
        pickle.dump({"graph_nodes": {}}, f)
    with (target_dir / "graph_edges.pkl").open("wb") as f:
        pickle.dump({"graph_edges": {}}, f)
    inverted = {
        tok: [{"chunk_id": _FIXTURE_CHUNK_ID, "score": 5.0}]
        for tok in set(_tokenize(_FIXTURE_CONTENT))
    }
    with (target_dir / "inverted_index.pkl").open("wb") as f:
        pickle.dump({"inverted_index": inverted}, f)


def _knowledge_launch(tmp_path: Path) -> KnowledgeServerLaunchConfig:
    repo = os.environ.get("GATEWAY_TEST_KNOWLEDGE_REPO")
    if not repo:
        pytest.fail(
            "GATEWAY_TEST_KNOWLEDGE_REPO unset — point it at a cic-mcp-knowledge "
            "checkout (real-subprocess evidence test, not skipped)."
        )
    repo_root = Path(repo)
    python_exe = os.environ.get("GATEWAY_TEST_KNOWLEDGE_PYTHON")
    kb_dir = tmp_path / "fixture_kb"
    _build_fixture_kb(kb_dir)
    return KnowledgeServerLaunchConfig(
        repo_root=repo_root,
        python_executable=Path(python_exe) if python_exe else None,
        kb_data_dir=kb_dir,
    )


def _shared_config() -> SharedDbConfig:
    config = SharedDbConfig.from_env()
    try:
        with psycopg.connect(config.conninfo(), connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 — fail loudly, do not skip
        pytest.fail(
            f"Postgres unreachable via SESSION_STORE_PG_* ({config.host}:{config.port}/"
            f"{config.dbname}): {exc} — real-evidence test, not skipped."
        )
    return config


_CANDIDATES_DDL = """
CREATE SCHEMA IF NOT EXISTS shared_core;
CREATE TABLE IF NOT EXISTS shared_core.candidates (
    candidate_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword_description TEXT NOT NULL,
    trust               TEXT NOT NULL
        CONSTRAINT candidates_trust_valid_values
        CHECK (trust IN ('mixed', 'candidate', 'reviewed_shared')),
    canonical           BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT candidates_canonical_requires_reviewed_shared
        CHECK (canonical = FALSE OR trust = 'reviewed_shared'),
    weight_score        DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_evidence_at    TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _seed_candidates(config: SharedDbConfig, marker: str) -> dict[str, str]:
    """Insert three rows — one per trust value — all matching `marker`.
    Returns {trust: keyword_description}. Only candidate + reviewed_shared
    must surface; mixed must be excluded.
    """
    rows = {
        "mixed": f"{marker} mixed-trust unreviewed cross-session note",
        "candidate": f"{marker} candidate-trust cross-session note",
        "reviewed_shared": f"{marker} reviewed_shared promoted cross-session note",
    }
    with psycopg.connect(config.conninfo()) as conn:
        conn.execute(_CANDIDATES_DDL)
        for trust, desc in rows.items():
            conn.execute(
                "INSERT INTO shared_core.candidates "
                "(keyword_description, trust, weight_score) VALUES (%s, %s, %s)",
                (desc, trust, 1.0 if trust == "reviewed_shared" else 0.5),
            )
        conn.commit()
    return rows


# --------------------------------------------------------------------------
# 1. knowledge adapter — real subprocess
# --------------------------------------------------------------------------
def test_knowledge_adapter_real_subprocess(tmp_path):
    launch = _knowledge_launch(tmp_path)
    facts = asyncio.run(search_knowledge(launch, _FIXTURE_QUERY, top_k=5))

    assert facts, "knowledge adapter returned no canonical facts for fixture query"
    fact = facts[0]
    # content actually fetched via get_chunk (server's search_query omits bodies)
    assert "ProofTrace" in fact["content"]
    assert fact["ref"] == f"knowledge:chunk:{_FIXTURE_CHUNK_ID}"
    # canonical_facts carry NO trust field — placement IS the canonical mark.
    assert "trust" not in fact
    # The envelope-shaped projection must be exactly {content, ref}:
    projected = {"content": fact["content"], "ref": fact["ref"]}
    assert set(projected) == {"content", "ref"}


# --------------------------------------------------------------------------
# 2. shared adapter — real Postgres, mixed excluded, trust preserved
# --------------------------------------------------------------------------
def test_shared_adapter_excludes_mixed_and_preserves_trust():
    config = _shared_config()
    marker = f"gwksa-{uuid.uuid4().hex[:12]}"
    expected = _seed_candidates(config, marker)

    notes = search_shared_candidates(config, marker, limit=10)

    trust_by_content = {n["content"]: n["trust"] for n in notes}
    # mixed row must NOT surface
    assert expected["mixed"] not in trust_by_content
    # candidate + reviewed_shared must surface, trust PRESERVED verbatim
    assert trust_by_content.get(expected["candidate"]) == "candidate"
    assert trust_by_content.get(expected["reviewed_shared"]) == "reviewed_shared"
    # every returned trust is in the allowed set, never 'mixed'
    assert all(n["trust"] in ALLOWED_SHARED_TRUST for n in notes)
    # ref shape
    assert all(n["ref"].startswith("shared:candidate:") for n in notes)


# --------------------------------------------------------------------------
# 3. multi-source envelope — BOTH real sources, per-element trust preserved
# --------------------------------------------------------------------------
def test_multi_source_envelope_preserves_per_element_trust(tmp_path):
    launch = _knowledge_launch(tmp_path)
    config = _shared_config()
    marker = _FIXTURE_QUERY  # shared rows must match the SAME query token
    _seed_candidates(config, marker)

    sources_used: list[dict] = []
    refs: list[dict] = []
    canonical_facts, shared_memory_notes = asyncio.run(
        _gather_multi_source(
            query=_FIXTURE_QUERY,
            knowledge_launch=launch,
            shared_config=config,
            knowledge_top_k=5,
            shared_limit=10,
            sources_used=sources_used,
            refs=refs,
        )
    )

    # ≥1 knowledge element AND ≥1 shared element (input.md requirement)
    assert len(canonical_facts) >= 1
    assert len(shared_memory_notes) >= 1

    # knowledge -> canonical_facts: {content, ref} ONLY, no trust field
    for fact in canonical_facts:
        assert set(fact) == {"content", "ref"}

    # shared -> shared_memory_notes: trust PRESERVED, never 'mixed', never canonical
    for note in shared_memory_notes:
        assert set(note) == {"content", "trust", "ref"}
        assert note["trust"] in ALLOWED_SHARED_TRUST

    # assemble the real envelope and assert the trust contract end-to-end
    envelope = _build_envelope(
        session_id="sess-multisource-test",
        answer_type="history_recall",
        sources_used=sources_used,
        session_derived_notes=[],
        refs=refs,
        proof_requirements=[],
        per_category_overrides={
            "session_derived_notes": "not_used",
            "canonical_facts": "high" if canonical_facts else "not_used",
            "shared_memory_notes": _shared_per_category(shared_memory_notes),
        },
        canonical_facts=canonical_facts,
        shared_memory_notes=shared_memory_notes,
    )

    # canonical content present -> overall_confidence "high" (derived)
    assert envelope["trust_summary"]["overall_confidence"] == "high"
    assert envelope["trust_summary"]["per_category"]["canonical_facts"] == "high"
    assert envelope["trust_summary"]["per_category"]["shared_memory_notes"] in (
        "low",
        "medium",
    )
    # both sources recorded as consulted
    consulted = {s["source_id"] for s in envelope["sources_used"]}
    assert "cic-mcp-knowledge" in consulted
    assert "cic-mcp-shared" in consulted
    # NO canonical_fact leaked a trust field; NO shared note reached canonical
    assert all("trust" not in f for f in envelope["canonical_facts"])
    assert envelope["workdir_facts"] == []
