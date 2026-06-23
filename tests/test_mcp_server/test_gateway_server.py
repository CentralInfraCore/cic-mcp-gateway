"""End-to-end test for mcp-server/gateway_server.py's get_gateway_context_pack tool.

Job: gateway-context-pack-production-wiring-001, "Feladat" 3 ("Valós,
futtatott bizonyíték"). This is the FIRST test that proves a real
production call site exists for gateway_core.compile_context.
compile_context() — before this job it was called ONLY by its own module
and by tests/test_gateway_core/test_compile_context.py.

This test exercises the FULL real path, one level above
test_compile_context.py:
  1. a real cic-mcp-session ingest pipeline run (insert_envelope ->
     run_projection_batch -> run_indexing_batch), against a REAL Postgres
     instance — IDENTICAL fixture chain to
     tests/test_gateway_core/test_compile_context.py (seeded_session_id,
     pg_config, session_repo_root) — NOT reinvented, copied field-for-field
     per input.md "Feladat" 3 ("a `test_compile_context.py` MEGLÉVŐ
     fixture-mintáját követve").
  2. starting THIS repo's OWN NEW mcp-server/gateway_server.py as a REAL,
     independent subprocess and talking to it via REAL mcp.client.stdio
     (NOT an in-process Python call of get_gateway_context_pack(), and NOT
     a mock) — same evidence bar as test_compile_context.py's own
     compile_context() subprocess proof.
  3. calling the get_gateway_context_pack tool over that real stdio MCP
     connection, for the real seeded session_id.
  4. asserting that the returned GatewayContextEnvelope contains at least
     one session_derived_notes[] entry whose ref contains ":chunk:" (NOT
     just a get_session_status() summary note) — the SAME hardened
     assertion as gateway-compile-context-test-hardening-001's
     test_compile_context_available_session_end_to_end, one hop further
     down the call chain (MCP tool -> compile_context() -> session
     subprocess -> Postgres).

Requires (identical to tests/test_gateway_core/test_compile_context.py):
  - a reachable Postgres instance with ALL cic-mcp-session schema/
    migration files already applied, addressed via the SESSION_STORE_PG_*
    env vars below.
  - SESSION_CONTEXT_PACK_TEST_SESSION_REPO env var pointing at a
    cic-mcp-session checkout that has .venv-host/bin/python already built
    (`make deps.local` in that checkout) — this test (via
    gateway_server.py -> compile_context()) launches THAT checkout's
    session_server.py as the real MCP subprocess, and also imports ITS
    session_store package (via sys.path) to drive the real ingest
    pipeline, since cic-mcp-session is a read-only dependency for this job
    (input.md "Nem cél": no copy of session_store is vendored into
    cic-mcp-gateway).

If SESSION_CONTEXT_PACK_TEST_SESSION_REPO is unset or Postgres is
unreachable, the test fails loudly (pytest.fail), same "do not silently
skip the real-evidence test" stance as test_compile_context.py.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

GATEWAY_REPO_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_SERVER_SCRIPT = GATEWAY_REPO_ROOT / "mcp-server" / "gateway_server.py"


def _session_repo_root() -> Path:
    raw = os.environ.get("SESSION_CONTEXT_PACK_TEST_SESSION_REPO")
    if not raw:
        pytest.fail(
            "SESSION_CONTEXT_PACK_TEST_SESSION_REPO is not set — point it at a "
            "cic-mcp-session checkout with .venv-host/bin/python already built "
            "(make deps.local) and ALL schema/migration SQL files already "
            "applied to the target Postgres instance."
        )
    path = Path(raw).resolve()
    if not (path / "session_store").is_dir():
        pytest.fail(f"{path} does not look like a cic-mcp-session checkout (no session_store/)")
    return path


@pytest.fixture(scope="module")
def session_repo_root() -> Path:
    return _session_repo_root()


@pytest.fixture(scope="module", autouse=True)
def _add_session_repo_to_path(session_repo_root: Path):
    """Make cic-mcp-session's OWN session_store package importable, so this
    test can call the REAL insert_envelope/run_projection_batch/
    run_indexing_batch functions — no reimplementation, no copy. Identical
    pattern to tests/test_gateway_core/test_compile_context.py.
    """
    sys.path.insert(0, str(session_repo_root))
    sys.path.insert(0, str(GATEWAY_REPO_ROOT))
    yield
    sys.path.remove(str(session_repo_root))
    sys.path.remove(str(GATEWAY_REPO_ROOT))


@pytest.fixture(scope="module")
def pg_config(_add_session_repo_to_path):
    import psycopg
    from session_store.envelope_writer import SessionStoreConfig

    cfg = SessionStoreConfig(
        host=os.environ.get("SESSION_STORE_PG_HOST", "localhost"),
        port=int(os.environ.get("SESSION_STORE_PG_PORT", "55436")),
        dbname=os.environ.get("SESSION_STORE_PG_DB", "testdb"),
        user=os.environ.get("SESSION_STORE_PG_USER", "postgres"),
        password=os.environ.get("SESSION_STORE_PG_PASSWORD", "test"),
    )
    try:
        with psycopg.connect(cfg.conninfo(), connect_timeout=5):
            pass
    except psycopg.OperationalError as exc:
        pytest.fail(
            "Cannot reach a real Postgres instance for the gateway_server.py "
            f"end-to-end test. Original error: {exc}"
        )
    # Propagate to the env so BOTH subprocess hops (gateway_server.py's own
    # compile_context() call, and THAT call's own session_server.py
    # subprocess) target the SAME instance as this test's own direct
    # pipeline calls.
    os.environ["SESSION_STORE_PG_HOST"] = cfg.host
    os.environ["SESSION_STORE_PG_PORT"] = str(cfg.port)
    os.environ["SESSION_STORE_PG_DB"] = cfg.dbname
    os.environ["SESSION_STORE_PG_USER"] = cfg.user
    os.environ["SESSION_STORE_PG_PASSWORD"] = cfg.password
    return cfg


def _valid_envelope(**overrides) -> dict:
    """Mirrors tests/test_gateway_core/test_compile_context.py:_valid_envelope
    exactly (field-for-field) — not reinvented.
    """
    base = {
        "apiVersion": "cic.session/v1",
        "kind": "SessionIngressEnvelope",
        "event_id": str(uuid.uuid4()),
        "provider": "claude-code",
        "provider_session_id": "gateway-pytest-session",
        "provider_event_name": "Stop",
        "source": {"kind": "hook", "collector": "log-event.py"},
        "occurred_at": datetime(2026, 6, 22, 13, 0, 0, tzinfo=timezone.utc),
        "ingested_at": datetime(2026, 6, 22, 13, 0, 1, tzinfo=timezone.utc),
        "payload": {"raw_text": "hello world"},
        "payload_encoding": "json",
        "raw_payload_hash": "sha256:" + ("a" * 64),
        "trust": "session_local",
        "canonical": False,
        "interpreted": False,
        "idempotency_key": "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
        "workstream": None,
        "schema_notes": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def seeded_session_id(pg_config) -> str:
    """Drive ONE fresh session through the REAL ingest chain
    (insert_envelope -> run_projection_batch -> run_indexing_batch).
    Identical pattern to tests/test_gateway_core/test_compile_context.py's
    own seeded_session_id fixture. Uses a fresh provider_session_id per
    test run (uuid suffix) so this test does not depend on / interfere
    with any other seeded data in the same DB.
    """
    from session_store.chunk_indexer import run_indexing_batch
    from session_store.envelope_writer import insert_envelope
    from session_store.turn_projector import run_projection_batch

    provider_session_id = f"gateway-server-pytest-{uuid.uuid4().hex[:8]}"
    base_time = datetime(2026, 6, 22, 13, 0, 0, tzinfo=timezone.utc)
    turns = [
        ("Stop", "User: gateway_server.py end-to-end turn 1."),
        ("AssistantMessage", "Assistant: gateway_server.py end-to-end turn 2."),
    ]
    for i, (event_name, text) in enumerate(turns):
        envelope = _valid_envelope(
            event_id=str(uuid.uuid4()),
            provider_session_id=provider_session_id,
            provider_event_name=event_name,
            occurred_at=base_time + timedelta(minutes=i),
            ingested_at=base_time + timedelta(minutes=i, seconds=1),
            payload={"raw_text": text},
            idempotency_key="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
        )
        insert_envelope(envelope, config=pg_config)
        run_projection_batch(config=pg_config)
        run_indexing_batch(config=pg_config)

    import psycopg

    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id FROM session_core.sessions WHERE provider_session_id = %s",
                (provider_session_id,),
            )
            row = cur.fetchone()
            assert row is not None, "real pipeline did not produce a session_core.sessions row"
            return str(row[0])


async def _call_gateway_context_pack(session_id: str, session_repo_root: Path) -> dict:
    """Start mcp-server/gateway_server.py as a REAL subprocess (this
    repo's OWN .venv-host/bin/python — the gateway_server.py process
    itself only needs the `mcp` package to run; it imports
    gateway_core.compile_context, which in turn launches the cic-mcp-
    session subprocess using session_repo_root's OWN .venv-host/bin/
    python, exactly as gateway_core/compile_context.py:
    SessionServerLaunchConfig.to_stdio_params() already does), perform a
    real stdio MCP handshake, and call get_gateway_context_pack.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    gateway_python = GATEWAY_REPO_ROOT / ".venv-host" / "bin" / "python"
    env = {"PYTHONPATH": str(GATEWAY_REPO_ROOT)}
    for var in (
        "SESSION_STORE_PG_HOST",
        "SESSION_STORE_PG_PORT",
        "SESSION_STORE_PG_DB",
        "SESSION_STORE_PG_USER",
        "SESSION_STORE_PG_PASSWORD",
    ):
        value = os.environ.get(var)
        if value is not None:
            env[var] = value

    server_params = StdioServerParameters(
        command=str(gateway_python),
        args=[str(GATEWAY_SERVER_SCRIPT)],
        env=env,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_gateway_context_pack",
                {
                    "session_id": session_id,
                    "session_repo_root": str(session_repo_root),
                },
            )

    import json

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
        return structured["result"]
    if structured is not None:
        return structured

    content = getattr(result, "content", None) or []
    if content and getattr(content[0], "text", None) is not None:
        return json.loads(content[0].text)
    pytest.fail(f"get_gateway_context_pack returned no decodable content: {result!r}")


def test_get_gateway_context_pack_available_session_end_to_end(
    session_repo_root, seeded_session_id
):
    """Full real path, ONE level above test_compile_context.py: real DB
    data (seeded via the real pipeline) + a real gateway_server.py
    subprocess + a real stdio MCP handshake to THAT subprocess + the
    get_gateway_context_pack tool call (which internally calls
    compile_context(), which itself starts a SECOND real subprocess for
    cic-mcp-session/mcp-server/session_server.py) -> schema-relevant
    GatewayContextEnvelope.
    """
    import asyncio

    envelope = asyncio.run(
        _call_gateway_context_pack(seeded_session_id, session_repo_root)
    )

    assert envelope["kind"] == "GatewayContextEnvelope"
    assert envelope["scope"]["session_id"] == seeded_session_id
    assert envelope["proof_requirements"] == []
    assert len(envelope["session_derived_notes"]) >= 1
    assert all(
        note["trust"] in ("session_local", "session_derived")
        for note in envelope["session_derived_notes"]
    )

    # Hardened assertion, mirroring gateway-compile-context-test-
    # hardening-001's test_compile_context_available_session_end_to_end:
    # require AT LEAST ONE note that is actually derived from the context
    # pack's chunk content (ref containing ":chunk:"), so this test fails
    # loudly if the real pipeline silently degraded to status-only, ONE
    # level above compile_context()'s own test — proving the MCP tool ->
    # compile_context() -> session subprocess -> Postgres chain end to end.
    chunk_refs = [
        n for n in envelope["session_derived_notes"] if ":chunk:" in n["ref"]
    ]
    assert len(chunk_refs) >= 1, (
        "context_pack tartalom hiányzik a session_derived_notes[]-ból a "
        "get_gateway_context_pack MCP tool hívás eredményében — csak a "
        "get_session_status() összegző note van jelen, a valódi "
        "chunk-eredetű tartalom hiányzik"
    )


def test_get_gateway_context_pack_unavailable_session_end_to_end(session_repo_root, pg_config):
    """Full real path for the negative case, ONE level above
    test_compile_context.py: a session_id that genuinely does not exist in
    session_core.sessions must surface via proof_requirements[], never via
    a silent/empty-but-"successful" envelope, even through the MCP tool
    layer.
    """
    import asyncio

    nonexistent_session_id = str(uuid.uuid4())
    envelope = asyncio.run(
        _call_gateway_context_pack(nonexistent_session_id, session_repo_root)
    )

    assert envelope["session_derived_notes"] == []
    assert len(envelope["proof_requirements"]) == 1
    assert nonexistent_session_id in envelope["proof_requirements"][0]["description"]
    assert envelope["trust_summary"]["per_category"]["session_derived_notes"] == "unverified"
