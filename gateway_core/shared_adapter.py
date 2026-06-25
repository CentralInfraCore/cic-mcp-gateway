"""shared_adapter — the cic-mcp-shared source adapter for the gateway.

Job: gateway-knowledge-shared-adapters-001. The THIRD real source wired into
compile_context() (after cic-mcp-session and cic-mcp-knowledge). It performs
a minimal, READ-ONLY direct Postgres query against shared_core.candidates
and produces shared_memory_notes[] entries for the GatewayContextEnvelope.

Why a direct DB read, not an MCP subprocess (unlike knowledge/session):
cic-mcp-shared exposes its candidates as a relational store
(shared_core.candidates, see cic-mcp-shared/output/
shared-core-storage-schema.sql); there is no shared MCP query server in this
job's scope. The gateway only READS — it never writes, promotes, or mutates
shared_core (canonical promotion is explicitly "Nem" for the gateway, see
cic-mcp-gateway/CLAUDE.md "Fő határok"). cic-mcp-shared is a READ-ONLY
dependency for this job.

Trust contract (the load-bearing rule of this adapter):
  - shared_memory_notes items carry their OWN `trust` (schema enum:
    mixed / candidate / reviewed_shared) — the gateway PRESERVES the row's
    stored trust verbatim, it never upgrades it.
  - `mixed`-trust rows are EXCLUDED entirely: only trust IN
    ('candidate', 'reviewed_shared') rows may enter the envelope. `mixed`
    is unreviewed/contradictory cross-session material and must not surface
    as gateway-served context.
  - shared content NEVER goes into canonical_facts[] (that is knowledge-
    only); even a `reviewed_shared` row is "not canonical by default".

Config (NOT reinvented): SharedDbConfig mirrors cic-mcp-shared's own
SharedStoreConfig.from_env() — the SAME SESSION_STORE_PG_* env var names —
so the gateway reads the same Postgres instance the shared aggregator wrote
to, with no extra wiring.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

SOURCE_ID_SHARED = "cic-mcp-shared"
TRUST_DOMAIN_SHARED = "shared"

# The ONLY trust values the gateway is allowed to surface from
# shared_core.candidates. 'mixed' is deliberately absent — see module
# docstring "Trust contract". This tuple is used verbatim in the SQL WHERE
# clause AND re-asserted on every returned row (defense in depth: even if
# the query were ever broadened, a stray 'mixed' row would still be dropped).
ALLOWED_SHARED_TRUST = ("candidate", "reviewed_shared")


@dataclass(frozen=True)
class SharedDbConfig:
    """DB connection parameters for the READ-ONLY shared_core.candidates
    query — same SESSION_STORE_PG_* var names as cic-mcp-shared's own
    SharedStoreConfig.from_env() (this job's tests point the gateway read
    AND the shared INSERT at the SAME Postgres instance). No hardcoded DSN.
    """

    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "SharedDbConfig":
        return cls(
            host=os.environ.get("SESSION_STORE_PG_HOST", os.environ.get("PGHOST", "localhost")),
            port=int(os.environ.get("SESSION_STORE_PG_PORT", os.environ.get("PGPORT", "5432"))),
            dbname=os.environ.get("SESSION_STORE_PG_DB", os.environ.get("PGDATABASE", "postgres")),
            user=os.environ.get("SESSION_STORE_PG_USER", os.environ.get("PGUSER", "postgres")),
            password=os.environ.get(
                "SESSION_STORE_PG_PASSWORD", os.environ.get("PGPASSWORD", "")
            ),
        )

    def conninfo(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )


# READ-ONLY. Parameterized trust list + keyword ILIKE. mixed-trust rows can
# never match (the IN list is ALLOWED_SHARED_TRUST, which excludes 'mixed').
# Ordered by weight_score so the most-reinforced candidates surface first.
_SEARCH_SQL = """
    SELECT candidate_id, keyword_description, trust, weight_score
    FROM shared_core.candidates
    WHERE trust = ANY(%(allowed_trust)s)
      AND keyword_description ILIKE %(keyword)s
    ORDER BY weight_score DESC, last_evidence_at DESC NULLS LAST
    LIMIT %(limit)s
"""


def search_shared_candidates(
    config: SharedDbConfig,
    keyword: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """READ-ONLY query of shared_core.candidates -> shared_memory_note-shaped
    items.

    Each returned dict has the shape compile_context() folds into the
    envelope's shared_memory_notes[] / refs[]:
        {
          "content": <keyword_description>,
          "trust": <row.trust>,          # PRESERVED verbatim (candidate|reviewed_shared)
          "ref": "shared:candidate:<candidate_id>",
          "candidate_id": <candidate_id>,
          "weight_score": <weight_score>,
        }
    `mixed`-trust rows are excluded by the query AND re-checked here. No
    write/DDL is ever issued — the connection only runs the SELECT above.
    """
    rows: list[dict[str, Any]]
    with psycopg.connect(config.conninfo()) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                _SEARCH_SQL,
                {
                    "allowed_trust": list(ALLOWED_SHARED_TRUST),
                    "keyword": f"%{keyword}%",
                    "limit": limit,
                },
            )
            rows = cur.fetchall()

    notes: list[dict[str, Any]] = []
    for row in rows:
        trust = row["trust"]
        # Defense in depth: never let a non-allowed trust through even if the
        # query were ever broadened (the load-bearing rule of this adapter).
        if trust not in ALLOWED_SHARED_TRUST:
            continue
        notes.append(
            {
                "content": row["keyword_description"],
                "trust": trust,
                "ref": f"shared:candidate:{row['candidate_id']}",
                "candidate_id": str(row["candidate_id"]),
                "weight_score": row["weight_score"],
            }
        )
    return notes
