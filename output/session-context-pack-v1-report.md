# session-context-pack-v1-001 Output

## Scope

Ez a job az ELSŐ valódi, futtatott `compile_context()` implementáció a `cic-mcp-gateway`
repóban. A `gateway-session-adapter-contract-001` job kontraktus-szinten definiálta a
`GatewayContextEnvelope` összeállításának elvét — ez a job azt **bizonyítja** valódi
subprocess-alapú MCP handshake-kel, valódi Postgres pipeline-on átfutott adattal, és
programozottan validált kimenettel.

Implementált modul: `gateway_core/compile_context.py`  
Validator modul: `gateway_core/validate_envelope.py`  
Automatizált teszt: `tests/test_gateway_core/test_compile_context.py`

Scope-korlátozások (per input.md "Nem cél"):
- kizárólag a `cic-mcp-session` forrás van bekötve (`cic-mcp-knowledge`, `cic-mcp-shared`,
  `cic-mcp-workdir` nem — ezek üres tömbként jelennek meg, ami schema-érvényes)
- `query_intent` ebben az implementációban rögzített `"session-context-recall"`
- a 7 tool közül 2 hívódik: `get_session_status()` (mindig, először) + `get_session_context_pack()`

## Inputs Read

- `cic-mcp-factory/.cic-context/factory-docs/execution-phases.md` — "Phase 2" szekció
- `cic-mcp-factory/.cic-context/factory-docs/architecture.md` — "Fő határok" szekció
- `cic-mcp-gateway/output/gateway-context-envelope.schema.yaml` — **teljes schema**, minden kötelező mezővel (16 required mező, properties, enum, forbidden_combinations)
- `cic-mcp-gateway/output/gateway-session-adapter-contract.md` — "Session MCP API Surface", "Adapter Input/Output Contract", "Trust Mapping", "Unavailable-Session Behavior" szekciók — **ez a kontraktus, amit implementáltunk**
- `cic-mcp-session/mcp-server/session_server.py` — a 7 `@mcp.tool()` regisztráció (teljes fájl, 457 sor)
- `cic-mcp-session/tests/test_session_store/test_session_api.py` — 158-169. sor: `_run_chain_for_envelope()` minta (`insert_envelope` → `run_projection_batch` → `run_indexing_batch`) — **ezt a mintát követtük**
- `cic-mcp-session/session_store/envelope_writer.py` — `SessionStoreConfig.from_env()`, `insert_envelope()`
- `cic-mcp-session/session_store/turn_projector.py` — `run_projection_batch()`
- `cic-mcp-session/session_store/chunk_indexer.py` — `run_indexing_batch()`
- `cic-mcp-session/output/session-mcp-venv-fix-report.md` — a stdio MCP handshake bizonyítási mintája (`.venv-host/bin/python`, `PYTHONPATH`, `mcp.client.stdio`)

## Test Session Data Setup

### Postgres konténer

A `session-context-pack-test` Docker konténer (pgvector/pgvector:pg16, port 55436,
`testdb` adatbázis) már futott az adott workspace-ben, a cic-mcp-session migrációk
(`session-postgres-schema.sql`, `session-chunk-indexer-migration.sql`,
`session-retrieval-quality-migration.sql`, `session-vector-search-api-migration.sql`,
`session-source-refs-api-migration.sql`) már alkalmazva.

### Valódi pipeline-futtatás

A `test_session_api.py` `_run_chain_for_envelope()` mintáját követve (158-169. sor) futtattuk
a teljes pipeline-t 4 turn-re:

```python
from session_store.envelope_writer import insert_envelope
from session_store.turn_projector import run_projection_batch
from session_store.chunk_indexer import run_indexing_batch

provider_session_id = "gateway-seed-76cbd8a1"
turns = [
    ("Stop",               "User: Kérem adjuk hozzá a compile_context() implementációt a gateway-hoz."),
    ("AssistantMessage",   "Assistant: Megértettem, a compile_context() függvényt a gateway_core/compile_context.py-ba helyezem."),
    ("Stop",               "User: Melyik trust értéket kapja a get_session_context_pack visszatérési értéke?"),
    ("AssistantMessage",   "Assistant: session_derived értéket, mivel aggregált view-t ad vissza."),
]
for i, (event_name, text) in enumerate(turns):
    envelope = _valid_envelope(provider_session_id=provider_session_id, ...)
    insert_envelope(envelope, config=pg_config)       # insert_id=14,15,16,17
    run_projection_batch(config=pg_config)
    run_indexing_batch(config=pg_config)
```

**Tényleges parancs kimenet:**

```
Warning: ... HF_TOKEN ...
Loading weights: 100%|██████████| 199/199 [00:00<00:00, 10879.81it/s]
Turn 1: insert_id=14, event=Stop
Turn 2: insert_id=15, event=AssistantMessage
Turn 3: insert_id=16, event=Stop
Turn 4: insert_id=17, event=AssistantMessage

Session ID: b20ed1bc-a2cb-4a00-a087-1f6ce9d8f7ab
Total chunks in DB: 13
Total sessions in DB: 6

provider_session_id: gateway-seed-76cbd8a1
```

**DB sorszámok ellenőrzése (psql):**

```sql
-- session_core.sessions
SELECT session_id, provider_session_id, status
FROM session_core.sessions
WHERE provider_session_id LIKE 'gateway-seed-%';
-- → b20ed1bc-a2cb-4a00-a087-1f6ce9d8f7ab | gateway-seed-76cbd8a1 | open

-- session_core.chunks a seeded session-re
SELECT count(*) FROM session_core.chunks c
JOIN session_core.turns t ON c.turn_id = t.turn_id
JOIN session_core.sessions s ON t.session_id = s.session_id
WHERE s.provider_session_id LIKE 'gateway-seed-%';
-- → 4 (4 turn = 4 chunk)
```

Bizonyítva: a 4 turn a VALÓDI `insert_envelope` → `run_projection_batch` → `run_indexing_batch`
pipeline-on futott át — kézzel írt SQL INSERT **nem volt**.

## compile_context() Implementation Summary

**Modul helye:** `gateway_core/compile_context.py`

**Választás indoklása:** A `cic-mcp-gateway` repóban a `gateway_core/` könyvtár az EGYETLEN
gateway-specifikus Python csomag (nem a `base-repo` örökség). Ebbe illeszkedik logikusan a
`compile_context.py` mint az első gateway-specifikus implementációs modul. A `gateway_core/`
könyvtár a korábbi `feature/session-context-pack-v1-001` branch munkái során lett létrehozva
(a branch már feature branch-ként létezett a klónban).

**Fő szerkezet:**

| Függvény | Fájl:sor | Leírás |
|---|---|---|
| `SessionServerLaunchConfig.to_stdio_params()` | `gateway_core/compile_context.py:81` | `.venv-host/bin/python` + `session_server.py` + `PYTHONPATH` összeállítása |
| `_compile_context_async()` | `gateway_core/compile_context.py:152` | Async implementáció, valódi stdio handshake |
| `compile_context()` | `gateway_core/compile_context.py:354` | Szinkron belépési pont, `asyncio.run()` wrapper |
| `_decode_tool_result()` | `gateway_core/compile_context.py:269` | MCP SDK wire format dekódolás (`TextContent[0].text` → JSON) |

**Adapter contract megfelelés:**

1. `get_session_status()` MINDIG ELSŐ (`compile_context.py:179`) — a "Unavailable-Session Behavior" gate
2. Ha session létezik: `get_session_context_pack()` (`compile_context.py:233`) — `query_intent = "session-context-recall"`
3. Trust mapping: status summary → `session_derived` (aggregált); context pack sorok → `session_derived` (aggregált view)
4. "Session nem elérhető" → `proof_requirements[]`, NEM `conflicts[]`

## Real Stdio MCP Handshake Evidence

**`@mcp.tool()` regisztrációk (grep kimenet, `cic-mcp-session/mcp-server/session_server.py`):**

```
$ grep -rn "@mcp.tool()" -A 1 mcp-server/session_server.py | grep -v test_
mcp-server/session_server.py:94:@mcp.tool()
mcp-server/session_server.py-95-def search_session_context(session_id: str, query: str, limit: int = 20) -> list[dict]:
--
mcp-server/session_server.py:150:@mcp.tool()
mcp-server/session_server.py-151-def search_session_context_fts(session_id: str, query: str, limit: int = 20) -> list[dict]:
--
mcp-server/session_server.py:199:@mcp.tool()
mcp-server/session_server.py-200-def search_session_context_vector(session_id: str, query: str, limit: int = 20) -> list[dict]:
--
mcp-server/session_server.py:258:@mcp.tool()
mcp-server/session_server.py-259-def get_session_timeline(session_id: str, limit: int = 100) -> list[dict]:
--
mcp-server/session_server.py:302:@mcp.tool()
mcp-server/session_server.py-303-def get_session_context_pack(session_id: str, max_chunks: int = 50) -> list[dict]:
--
mcp-server/session_server.py:348:@mcp.tool()
mcp-server/session_server.py-349-def get_session_status(session_id: str) -> dict:
--
mcp-server/session_server.py:395:@mcp.tool()
mcp-server/session_server.py-396-def get_session_source_refs(
```

**Valódi subprocess + stdio handshake — available session eset:**

A subprocess indítás bizonyítéka az MCP szerver saját log-kimenetéből (FastMCP INFO szint,
amelyet a szerver stderr-re ír a subprocess-ben):

```
[06/22/26 19:07:01] INFO Processing request of type CallToolRequest
                    INFO Processing request of type ListToolsRequest
                    INFO Processing request of type CallToolRequest
```

Értelmezés: 3 request érkezett a szerver oldalán:
1. `initialize()` / `ListToolsRequest` (a `ClientSession.initialize()` hívja)
2. `CallToolRequest` — `get_session_status()`
3. `CallToolRequest` — `get_session_context_pack()`

A subprocess a `mcp.client.stdio.stdio_client` + `ClientSession` mechanizmussal lett
indítva (`gateway_core/compile_context.py:169`):

```python
async with stdio_client(server_params) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        status_result = await session.call_tool("get_session_status", {"session_id": session_id})
        pack_result = await session.call_tool("get_session_context_pack", {"session_id": session_id, "max_chunks": max_chunks})
```

**Tényleges `compile_context()` kimenet (available session, session_id = `b20ed1bc-...`):**

```
kind: GatewayContextEnvelope
apiVersion: cic.gateway/v1
envelope_id: fd079c57-b1f6-4e4b-aedc-297734031c7e
created_at: 2026-06-22T17:07:01Z
query_intent: session-context-recall
answer_type: history_recall
scope: {'scope_kind': 'session', 'session_id': 'b20ed1bc-a2cb-4a00-a087-1f6ce9d8f7ab'}
sources_used (2 entries): [
  {
    "source_id": "cic-mcp-session",
    "trust_domain": "session_local",
    "query_capability_used": "status"
  },
  {
    "source_id": "cic-mcp-session",
    "trust_domain": "session_local",
    "query_capability_used": "context_pack"
  }
]
session_derived_notes count: 5
  note[0]: trust='session_derived', ref='session:b20ed1bc-...:status'
    content: "Session b20ed1bc-... status='open', started_at=2026-06-22..."
  note[1]: trust='session_derived', ref='session:b20ed1bc-...:chunk:40'
    content: 'User: Kérem adjuk hozzá a compile_context() implementációt a gateway-hoz.'
  note[2]: trust='session_derived', ref='session:b20ed1bc-...:chunk:41'
    content: 'Assistant: Megértettem, a compile_context() függvényt a gateway_core/compile_context.py-ba...'
  note[3]: trust='session_derived', ref='session:b20ed1bc-...:chunk:42'
    content: 'User: Melyik trust értéket kapja a get_session_context_pack visszatérési értéke?'
  note[4]: trust='session_derived', ref='session:b20ed1bc-...:chunk:43'
    content: 'Assistant: session_derived értéket, mivel aggregált view-t ad vissza.'
trust_summary: {"overall_confidence": "medium", "per_category": {"canonical_facts": "not_used", "workdir_facts": "not_used", "session_derived_notes": "medium", "shared_memory_notes": "not_used"}}
proof_requirements: []
refs count: 5
```

## Schema Validation Result

A `gateway_core/validate_envelope.py:validate_envelope_file()` függvény programozottan
bejárja a `gateway-context-envelope.schema.yaml` `required`/`properties`/`enum`/`const`/
`type`/`minItems`/`minLength` struktúráját — NOT vizuális átolvasás.

**Available session eset — 32/32 ellenőrzés `OK`:**

```
Schema validation: 32 checks passed
  OK: required key present: apiVersion
  OK: required key present: kind
  OK: required key present: envelope_id
  OK: required key present: created_at
  OK: required key present: query_intent
  OK: required key present: scope
  OK: required key present: answer_type
  OK: required key present: sources_used
  OK: required key present: trust_summary
  OK: required key present: canonical_facts
  OK: required key present: workdir_facts
  OK: required key present: session_derived_notes
  OK: required key present: shared_memory_notes
  OK: required key present: conflicts
  OK: required key present: proof_requirements
  OK: required key present: refs
  OK: type/shape OK: apiVersion
  OK: type/shape OK: kind
  OK: type/shape OK: envelope_id
  OK: type/shape OK: created_at
  OK: type/shape OK: query_intent
  OK: type/shape OK: scope
  OK: type/shape OK: answer_type
  OK: type/shape OK: sources_used
  OK: type/shape OK: canonical_facts
  OK: type/shape OK: workdir_facts
  OK: type/shape OK: session_derived_notes
  OK: type/shape OK: shared_memory_notes
  OK: type/shape OK: trust_summary
  OK: type/shape OK: conflicts
  OK: type/shape OK: proof_requirements
  OK: type/shape OK: refs
```

**Unavailable session eset — 32/32 ellenőrzés `OK`** (azonos validátor, azonos séma)

## Unavailable-Session Case — Real Output

**session_id: `00000000-0000-0000-0000-000000000000`** (szándékosan nem létező)

A subprocess log kimenet (a szerver stderr-je):

```
[06/22/26 19:07:13] INFO Processing request of type CallToolRequest
                    INFO Processing request of type ListToolsRequest
```

Értelmezés: csak 2 request — `initialize()` + `get_session_status()`. A `get_session_context_pack()`
**nem lett meghívva**, mert a státusz-ellenőrzés negatív volt (`{}` visszatérési érték).

**Tényleges visszatérési érték (`compile_context("00000000-0000-0000-0000-000000000000", ...`):**

```json
{
  "apiVersion": "cic.gateway/v1",
  "kind": "GatewayContextEnvelope",
  "envelope_id": "38afe492-26b0-45a5-89d7-80004f10bff9",
  "created_at": "2026-06-22T17:07:13Z",
  "query_intent": "session-context-recall",
  "scope": {
    "scope_kind": "session",
    "session_id": "00000000-0000-0000-0000-000000000000"
  },
  "answer_type": "status_summary",
  "sources_used": [
    {
      "source_id": "cic-mcp-session",
      "trust_domain": "session_local",
      "query_capability_used": "status"
    }
  ],
  "trust_summary": {
    "overall_confidence": "unverified",
    "per_category": {
      "canonical_facts": "not_used",
      "workdir_facts": "not_used",
      "session_derived_notes": "unverified",
      "shared_memory_notes": "not_used"
    }
  },
  "canonical_facts": [],
  "workdir_facts": [],
  "session_derived_notes": [],
  "shared_memory_notes": [],
  "conflicts": [],
  "proof_requirements": [
    {
      "description": "A kert session_id (00000000-0000-0000-0000-000000000000) nem feloldhato a cic-mcp-session retegben - get_session_status() ures eredmenyt adott, tehat a session_core.sessions tablaban nincs ehhez az ID-hez tartozo sor (vagy torolve lett, vagy soha nem letezett, vagy elgepelt ID). A session-scope-u tartalom emiatt nem kompilalhato, amig ez nem tisztazodik.",
      "blocking_for": [
        "scope.session_id:00000000-0000-0000-0000-000000000000"
      ]
    }
  ],
  "refs": []
}
```

**Kontraktus-megfelelés:** a `proof_requirements[]` tartalmaz 1 bejegyzést (NEM üres),
`session_derived_notes[]` üres, `trust_summary.per_category.session_derived_notes = "unverified"`
(NEM `"not_used"`) — pontosan a `gateway-session-adapter-contract.md` "Unavailable-Session
Behavior" 1-5. lépéseinek megfelelően.

## Automated Test Evidence

**Teszt fájl:** `tests/test_gateway_core/test_compile_context.py`

```
$ SESSION_STORE_PG_HOST=localhost SESSION_STORE_PG_PORT=55436 \
  SESSION_STORE_PG_DB=testdb SESSION_STORE_PG_USER=postgres SESSION_STORE_PG_PASSWORD=test \
  SESSION_CONTEXT_PACK_TEST_SESSION_REPO=<cic-mcp-session klón> \
  .venv-host/bin/python -m pytest tests/test_gateway_core/test_compile_context.py -v
```

**Kimenet:**

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.4.2, pluggy-1.6.0
rootdir: .../cic-mcp-gateway
configfile: pytest.ini
plugins: anyio-4.14.0, cov-7.0.0, mock-3.15.1
collecting ... collected 2 items

tests/test_gateway_core/test_compile_context.py::test_compile_context_available_session_end_to_end PASSED [ 50%]
tests/test_gateway_core/test_compile_context.py::test_compile_context_unavailable_session_end_to_end PASSED [100%]

================================ tests coverage ================================
...
============================== 2 passed in 2.70s ===============================
```

**2/2 teszt zöld.** Mindkét teszt a TELJES end-to-end utat futtatja:
- `test_compile_context_available_session_end_to_end`: valódi pipeline-on beadott session → valódi subprocess MCP handshake → schema-validált envelope
- `test_compile_context_unavailable_session_end_to_end`: nem létező session_id → `proof_requirements[]` jelzés → schema-validált envelope

## Findings

1. **A `_decode_tool_result()` helper szükséges volt.** Az MCP SDK 1.28.0 + FastMCP
   kombináció a `call_tool()` visszatérési értékét (list[dict] vagy dict) egyetlen JSON
   `TextContent` blokkban adja vissza (`.content[0].text`), NEM `.structuredContent`-ben.
   A `gateway_core/compile_context.py:269-292` ezt kezeli, és forward-compatible módon
   is ellenőrzi `.structuredContent`-et (jövőbeli SDK verziókhoz).

2. **A `StdioServerParameters.env` REPLACE, nem MERGE.** Amikor `env` paramétert adunk
   meg, az KIZÁRÓLAG azt tartalmazza — a subprocess nem örökli a szülő env-jét. Ezért a
   `SESSION_STORE_PG_*` env-változókat explicit át kell adni (`compile_context.py:56-62`
   `_SESSION_STORE_ENV_VARS`). Ez egy nem-nyilvánvaló MCP SDK viselkedés, amelynek hibás
   kezelése csendesen a `localhost:5432/postgres` default-ra esne vissza.

3. **A `gateway_core/` könyvtár a helyes modul-helyszín.** A `cic-mcp-gateway` repó
   jelenlegi struktúrájában (`CLAUDE.md` "Jelenlegi állapot": `source/` üres, `mcp-server/`
   a `base-repo` KB-szerver öröksége) a `gateway_core/` az EGYETLEN gateway-specifikus
   Python csomag — ide illeszkedik a `compile_context.py` is.

4. **A trust mapping konzisztens a kontraktussal.** `get_session_status()` → `session_derived`
   (aggregált), `get_session_context_pack()` → `session_derived` (aggregált view) —
   megegyezik a `gateway-session-adapter-contract.md` "Trust Mapping" táblájával.

5. **Scope-korlátozás explicit és schema-érvényes.** A `cic-mcp-knowledge`/`cic-mcp-shared`/
   `cic-mcp-workdir` hiánya üres tömb formájában jelenik meg (`canonical_facts: []`, stb.),
   ami a schema szerint `MAY be an empty array` — tehát érvényes, nem hiányos.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `insert_envelope` → `run_projection_batch` → `run_indexing_batch` pipeline VALÓDI futtatással, 4 turn bevitelével | proven | `insert_id=14,15,16,17`, session_id=`b20ed1bc-...`, 4 chunk a DB-ben — tényleges script kimenet idézve | script futtatva, kimenet idézve; DB COUNT idézve | low |
| `compile_context()` ÖNÁLLÓ subprocess-ként indítja a `cic-mcp-session` MCP szervert | proven | `[06/22/26 19:07:01] INFO Processing request of type CallToolRequest` — a szerver subprocess stderr-je idézve | tényleges subprocess stderr kimenet idézve | low |
| `compile_context()` valódi `mcp.client.stdio` stdio MCP handshake-kel hív | proven | `gateway_core/compile_context.py:169-181` `stdio_client` + `ClientSession` + `session.initialize()` + `session.call_tool()` idézve; 3 server-oldali request log idézve | file:line idézve + tényleges szerver log idézve | low |
| `get_session_status()` MINDIG ELSŐ, mielőtt bármilyen content-tool fut | proven | `compile_context.py:179-181` `get_session_status()` hívás; unavailable session esetén 2 server request (nem 3) — a pack-tool nem hívódik | file:line idézve + tényleges szerver log idézve | low |
| `get_session_context_pack()` hívódik available session esetén | proven | `compile_context.py:233-237`; server log: 3 request; 5 session_derived_notes (1 status + 4 chunk) | file:line idézve + kimenet idézve | low |
| A kimenet programozottan validálva a schema ellen — 32/32 ellenőrzés | proven | `gateway_core/validate_envelope.py:validate_envelope_file()` kimenet idézve (32 OK) | validator script futtatva, teljes kimenet idézve | low |
| "Session nem elérhető" eset valódi futtatással bizonyítva, `proof_requirements[]` megjelenik | proven | `compile_context("00000000-...", ...)` visszatérési értéke teljes JSON-ként idézve; `proof_requirements[0].description` tartalmazza a session_id-t | tényleges kimenet idézve | low |
| 2/2 pytest teszt zöld, valódi DB + subprocess + pipeline | proven | `2 passed in 2.70s` — pytest kimenet idézve | pytest lefuttatva, kimenet idézve | low |
| A `cic-mcp-session` klónba semmit nem commitoltunk | proven | a cic-mcp-session workspace read-only volt — nem nyitottunk fájlt írásra, nem futtattunk `git add`/`git commit` parancsot | szándékos scope-korlátozás | low |
| Schema-validáció programozottan (nem vizuális), `required`/`properties` bejárással | proven | `gateway_core/validate_envelope.py` — `_validate_object()`, `_validate_array()`, `_validate_node()` rekurzív walker, YAML schema betöltéssel | forráskód + futtatott kimenet idézve | low |

## Decisions Proposed

1. **`gateway_core/compile_context.py` a helyes modul-helyszín** — a `gateway_core/`
   csomag az egyetlen gateway-specifikus Python csomag a repóban, ide tartoznak a
   gateway-specifikus implementációs modulok.

2. **`_SESSION_STORE_ENV_VARS` explicit átadása subprocess env-be** — az MCP SDK
   `StdioServerParameters.env` REPLACE szemantikája miatt az env-változók átadása
   kötelező; ezt a `compile_context.py:56-62` implementálja.

3. **`_decode_tool_result()` helper szükséges** — a FastMCP + MCP SDK 1.28.0 kombináció
   a tool visszatérési értéket `TextContent[0].text` JSON-ban adja vissza, nem
   `.structuredContent`-ben; a helper forward-compatible is (ellenőrzi `.structuredContent`-et).

4. **Trust: mindkét tool → `session_derived`** — a `get_session_status()` aggregált
   status-összegzés, a `get_session_context_pack()` aggregált view — mindkettő
   `session_derived` a `gateway-session-adapter-contract.md` "Trust Mapping" táblája szerint.

## Rejected / Out Of Scope

- **Mock, in-process Python import, kézzel írt SQL INSERT** — explicit kizárva (input.md "Forbidden Shortcuts"); minden bizonyíték valódi futtatásból.
- **`cic-mcp-knowledge`/`cic-mcp-shared`/`cic-mcp-workdir` bekötése** — explicit kizárva (input.md "Nem cél").
- **Schema-fájlok módosítása** — nem történt; a schema érvényes az implementált kimenetekre.
- **`cic-mcp-session` repo módosítása** — nem történt; kizárólag olvasásra volt használva.
- **SSE-mód, autentikáció, multi-session kezelés** — explicit kizárva (input.md "Nem cél").
- **`meta.yaml` `status` mező módosítása** — nem módosítva.

## Risks

1. **`StdioServerParameters.env` REPLACE viselkedés** — dokumentált és kezelt
   (`_SESSION_STORE_ENV_VARS`), de ha a `cic-mcp-session` szerver jövőben új env-változókat
   igényel, azokat explicit fel kell venni ebbe a listába.

2. **MCP SDK verziófüggőség a `_decode_tool_result()`-ben** — a `TextContent[0].text`
   wire format empirikusan megfigyelt SDK 1.28.0 viselkedés; egy jövőbeli SDK verzió
   `.structuredContent`-et is feltölthet, de a helper forward-compatible (azt is ellenőrzi).

3. **A `cic-mcp-session` checkout `.venv-host/bin/python` kötelező** — ha a teszt-környezetben
   nincs `make deps.local` lefuttatva a `cic-mcp-session` klónban, a subprocess indítás
   sikertelen. Ez dokumentált elvárásfeltétel (`test_compile_context.py:23-31`).

4. **Scope-korlátozás — `query_intent` rögzített** — ez a v1 implementáció csak
   `"session-context-recall"` intent-et kezel; más `query_intent` értékek (pl.
   `"session-history-recall"`) egy jövőbeli v2 kibővítésben kezelhetők.

## Definition Of Done Check

- [x] teszt-session adat a VALÓDI `insert_envelope`/`run_projection_batch`/`run_indexing_batch` pipeline-on átfuttatva, DB-sorszámokkal bizonyítva
      → `insert_id=14,15,16,17`; `session_id=b20ed1bc-...`; 4 chunk; `SELECT count(*)` idézve
- [x] `compile_context()` implementálva, ÖNÁLLÓ subprocess + valódi stdio MCP handshake-kel hívja a `cic-mcp-session` szervert
      → `gateway_core/compile_context.py:169` `stdio_client` + `ClientSession`; szerver subprocess stderr log idézve
- [x] a kimenet programozottan validálva a `gateway-context-envelope.schema.yaml` ellen, kimenet idézve
      → `gateway_core/validate_envelope.py:validate_envelope_file()` — 32/32 OK, teljes lista idézve
- [x] "session nem elérhető" eset valódi futtatással bizonyítva, kimenet idézve
      → `compile_context("00000000-...", ...)` teljes JSON kimenet idézve; `proof_requirements[0]` megjelenik
- [x] legalább 1 automatizált teszt zöld, kimenet idézve
      → `2 passed in 2.70s` — pytest kimenet idézve
- [x] claim-evidence tábla kitöltve, nem üres
      → 10 sor, mind `proven` státusszal

**Összes DoD pont teljesült** — `status_after_merge: candidate` indokolt.

## Next Jobs

1. **`query_intent`-alapú routing kibővítése** — a jelenlegi v1 implementáció rögzített
   `"session-context-recall"` intent-et kezel; egy v2 job kibővítheti más intent-ekkel
   (`"session-history-recall"` → `get_session_timeline()`, `"session-search"` →
   `search_session_context()`).

2. **`get_session_source_refs()` bekötése `refs[]`-be** — a 7. tool, amely a provenance-
   referenciákat adja vissza, jelenleg nincs meghívva; egy jövőbeli job beköthetné a
   `refs[]` evidence-táblába, per `gateway-session-adapter-contract.md` "Adapter
   Input/Output Contract" utolsó sora.

3. **`cic-mcp-knowledge`/`cic-mcp-shared`/`cic-mcp-workdir` sources bekötése** — a többi
   trust-domain forrás adaptertje, amelyek feltöltik a `canonical_facts[]`,
   `shared_memory_notes[]`, `workdir_facts[]` mezőket.

4. **`gateway-source-registry-contract-001` patch** — a `query_capability_used`
   értékkészlet (`status`, `context_pack`) regisztrálása a `cic-mcp-session`
   registry-bejegyzés `query_capabilities[]` listájában (per `gateway-session-adapter-
   contract.md` "Decisions Proposed" 5. pont és "Risks" 1. tétele).
