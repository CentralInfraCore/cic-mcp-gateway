"""End-to-end test for gateway_core.compile_context.compile_context().

Job: session-context-pack-v1-001, "Feladat" 5 ("Automatizált teszt").

This test exercises the FULL real path:
  1. a real cic-mcp-session ingest pipeline run (insert_envelope ->
     run_projection_batch -> run_indexing_batch), against a REAL Postgres
     instance — same chain as
     cic-mcp-session/tests/test_session_store/test_session_api.py
     (_run_chain_for_envelope, lines ~158-169). NOT mocked, NOT a
     hand-written SQL INSERT.
  2. compile_context(), which starts the cic-mcp-session MCP server as a
     REAL, independent subprocess and talks to it via real
     mcp.client.stdio (NOT an in-process call, NOT a mock).
  3. structural schema validation of the resulting envelope against
     output/gateway-context-envelope.schema.yaml.

Requires:
  - a reachable Postgres instance with ALL cic-mcp-session schema/
    migration files already applied (see cic-mcp-session/tests/
    test_session_store/test_session_api.py module docstring for the exact
    `docker run` + `psql` commands and file order), addressed via the
    SESSION_STORE_PG_* env vars below.
  - SESSION_CONTEXT_PACK_TEST_SESSION_REPO env var pointing at a
    cic-mcp-session checkout that has .venv-host/bin/python built
    (`make deps.local` in that checkout) — this test launches THAT
    checkout's session_server.py as the real MCP subprocess, and also
    imports ITS session_store package (via sys.path) to drive the real
    ingest pipeline, since cic-mcp-session is a read-only dependency for
    this job (input.md "Nem cél": "a cic-mcp-session repo MÓDOSÍTÁSA" —
    no copy of session_store is vendored into cic-mcp-gateway).

If SESSION_CONTEXT_PACK_TEST_SESSION_REPO is unset or Postgres is
unreachable, the test fails loudly (pytest.fail), same "do not silently
skip the real-evidence test" stance as
cic-mcp-session/tests/test_session_store/test_session_api.py's own
pg_config fixture.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

GATEWAY_REPO_ROOT = Path(__file__).resolve().parents[2]


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
    run_indexing_batch functions — no reimplementation, no copy.
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
            "Cannot reach a real Postgres instance for the compile_context() "
            f"end-to-end test. Original error: {exc}"
        )
    # Propagate to the env so the compile_context() subprocess (which reads
    # SessionStoreConfig.from_env() inside session_server.py) targets the
    # SAME instance as this test's own direct pipeline calls.
    os.environ["SESSION_STORE_PG_HOST"] = cfg.host
    os.environ["SESSION_STORE_PG_PORT"] = str(cfg.port)
    os.environ["SESSION_STORE_PG_DB"] = cfg.dbname
    os.environ["SESSION_STORE_PG_USER"] = cfg.user
    os.environ["SESSION_STORE_PG_PASSWORD"] = cfg.password
    return cfg


def _valid_envelope(**overrides) -> dict:
    """Mirrors cic-mcp-session/tests/test_session_store/test_session_api.py
    :_valid_envelope exactly (field-for-field) — not reinvented.
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
    (insert_envelope -> run_projection_batch -> run_indexing_batch), same
    pattern as test_session_api.py:_run_chain_for_envelope. Uses a fresh
    provider_session_id per test run (uuid suffix) so this test does not
    depend on / interfere with any other seeded data in the same DB.
    """
    from session_store.chunk_indexer import run_indexing_batch
    from session_store.envelope_writer import insert_envelope
    from session_store.turn_projector import run_projection_batch

    provider_session_id = f"gateway-pytest-{uuid.uuid4().hex[:8]}"
    base_time = datetime(2026, 6, 22, 13, 0, 0, tzinfo=timezone.utc)
    turns = [
        ("Stop", "User: pytest end-to-end turn 1."),
        ("AssistantMessage", "Assistant: pytest end-to-end turn 2."),
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


def test_compile_context_available_session_end_to_end(session_repo_root, seeded_session_id):
    """Full real path: real DB data (seeded via the real pipeline) + real
    subprocess + real stdio MCP handshake + schema-valid envelope.
    """
    from gateway_core.compile_context import compile_context
    from gateway_core.validate_envelope import validate_envelope_file

    envelope = compile_context(seeded_session_id, repo_root=session_repo_root)

    assert envelope["kind"] == "GatewayContextEnvelope"
    assert envelope["scope"]["session_id"] == seeded_session_id
    assert envelope["proof_requirements"] == []
    assert len(envelope["session_derived_notes"]) >= 1
    assert all(note["trust"] in ("session_local", "session_derived") for note in envelope["session_derived_notes"])

    schema_path = GATEWAY_REPO_ROOT / "output" / "gateway-context-envelope.schema.yaml"
    checks = validate_envelope_file(envelope, schema_path)
    assert len(checks) > 0


def test_compile_context_unavailable_session_end_to_end(session_repo_root, pg_config):
    """Full real path for the negative case: a session_id that genuinely
    does not exist in session_core.sessions (no row ever inserted for it
    in this test run) must surface via proof_requirements[], never via a
    silent/empty-but-"successful" envelope.
    """
    from gateway_core.compile_context import compile_context
    from gateway_core.validate_envelope import validate_envelope_file

    nonexistent_session_id = str(uuid.uuid4())
    envelope = compile_context(nonexistent_session_id, repo_root=session_repo_root)

    assert envelope["session_derived_notes"] == []
    assert len(envelope["proof_requirements"]) == 1
    assert nonexistent_session_id in envelope["proof_requirements"][0]["description"]
    assert envelope["trust_summary"]["per_category"]["session_derived_notes"] == "unverified"

    schema_path = GATEWAY_REPO_ROOT / "output" / "gateway-context-envelope.schema.yaml"
    checks = validate_envelope_file(envelope, schema_path)
    assert len(checks) > 0
