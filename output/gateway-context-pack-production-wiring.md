# gateway-context-pack-production-wiring-001 Output

## Scope

Ez a job a Phase 6 ("Wiring") negyedik kódjobja. A `gateway_core/compile_context.py`
`compile_context()` függvény (job `session-context-pack-v1-001`, megerősítve
`gateway-compile-context-test-hardening-001`-ben) MÁR létezett, MÁR tesztelt valós
Postgres ellen — de NULLA production caller-rel: kizárólag a saját modulja és
`tests/test_gateway_core/test_compile_context.py` hívta.

A job EZT a hiányt zárja: létrehozott egy ÚJ, gateway-specifikus MCP szervert
(`mcp-server/gateway_server.py`), amely a `cic-mcp-session`-ben már bevált
`mcp-server/session_server.py` szétválasztási minta szerint KÜLÖN modul (NEM a
generikus `mcp-server/server.py` KB-szerver módosítása), és EGY `@mcp.tool()` tool-t
exponál (`get_gateway_context_pack`), ami TÉNYLEGESEN hívja a `compile_context()`-et.
Ez a TÉNYLEGES "production call site" — a CALL CHAIN megléte van bizonyítva, NEM
deployment.

A munka során egy valódi architekturális ütközést is meg kellett oldani: a
`compile_context()` szinkron belépési pontja saját `asyncio.run()`-t hív
(`gateway_core/compile_context.py:385`), de a FastMCP stdio transport már egy futó
event loop-on belül hívja meg a tool-függvényt — direkt hívás
`RuntimeError: asyncio.run() cannot be called from a running event loop`-ot
eredményez. A megoldás a HÍVÓ oldalon (`gateway_server.py`) történt: a tool
`async def`-té vált, és `loop.run_in_executor()`-ral egy worker thread-ben futtatja a
szinkron `compile_context()`-et — a `compile_context()` saját kódja NEM módosult,
NEM lett reimplementálva.

A `.venv-host` Python környezet a `cic-mcp-gateway` klónban korábban nem létezett —
ezt a jobnak fel kellett építenie (`python3 -m venv .venv-host` +
`pip install -r requirements.txt`), ugyanazzal a mintával, amit
`gateway-compile-context-test-hardening-001` már bizonyított.

## Inputs Read

- `${WORKDIR}/jobs/index.yaml` — `session-context-pack-v1-001` és
  `gateway-compile-context-test-hardening-001` `id:`/`status:` mezői
- `${WORKDIR}/.cic-context/factory-docs/architecture.md` — "cic-mcp-gateway" "Igen"
  lista, "agent-facing context API" sor
- `gateway_core/compile_context.py` — TELJES fájl, `compile_context()` (354-388. sor)
  teljes szignatúra és docstring, `_compile_context_async()` (152-266. sor),
  `SessionServerLaunchConfig` (69-101. sor)
- `tests/test_gateway_core/test_compile_context.py` — TELJES fájl, a
  `pg_config`/`seeded_session_id`/`session_repo_root` fixture-ök és a hardened
  `:chunk:`-ref asszerció
- `mcp-server/server.py` — referenciaként a FastMCP-induló minta (`mcp = FastMCP(...)`,
  `@mcp.tool()`, `mcp.run()`), NEM módosítva
- `cic-mcp-gateway/CLAUDE.md` — "Jelenlegi állapot" ("nincs még gateway-specifikus
  implementáció")
- `cic-mcp-session/mcp-server/session_server.py` — docstring top (1-20. sor), a
  "KÜLÖN modul, NEM a generikus KB-szerver módosítása" szétválasztási minta, és a
  `get_session_status()`/`get_session_context_pack()` tool-implementációk mintaként

## Prerequisite Check

```
$ grep -n '\- id: "session-context-pack-v1-001"' -A 3 jobs/index.yaml
107:  - id: "session-context-pack-v1-001"
108-    level: "capability"
109-    status: "done"
110-    parent: "gateway-session-adapter-contract-001"

$ grep -n '\- id: "gateway-compile-context-test-hardening-001"' -A 3 jobs/index.yaml
29:  - id: "gateway-compile-context-test-hardening-001"
30-    level: "capability"
31-    status: "done"
32-    parent: "session-context-pack-v1-001"
```

Mindkét prerequisite `status: "done"` az `id:` kulcs alatt → **GO**.

## New Gateway MCP Server — Call Site

Megerősítő grep-ek a forrásból:

```
$ grep -rn "^def compile_context" -A 15 gateway_core/compile_context.py | grep -v test_
gateway_core/compile_context.py:354:def compile_context(
gateway_core/compile_context.py-355-    session_id: str,
gateway_core/compile_context.py-356-    repo_root: Path | str,
gateway_core/compile_context.py-357-    max_chunks: int = 50,
gateway_core/compile_context.py-358-    python_executable: Path | str | None = None,
gateway_core/compile_context.py-359-) -> dict[str, Any]:
gateway_core/compile_context.py-360-    """Public, synchronous entry point.
...

$ grep -n "^def pg_config\|^def seeded_session_id\|^def session_repo_root" -A 3 tests/test_gateway_core/test_compile_context.py
69:def session_repo_root() -> Path:
70-    return _session_repo_root()
87:def pg_config(_add_session_repo_to_path):
88-    import psycopg
89-    from session_store.envelope_writer import SessionStoreConfig
146:def seeded_session_id(pg_config) -> str:
147-    """Drive ONE fresh session through the REAL ingest chain
148-    (insert_envelope -> run_projection_batch -> run_indexing_batch), same
149-    pattern as test_session_api.py:_run_chain_for_envelope. Uses a fresh
```

Új fájl: `mcp-server/gateway_server.py` (TELJES, KÜLÖN modul — `mcp-server/server.py`
nem módosult, lásd "Findings" alább a git status bizonyítékkal).

Saját FastMCP instance, `"cic-gateway"` néven (`mcp-server/gateway_server.py:49`):

```python
mcp = FastMCP("cic-gateway")
```

A tényleges production call site, `mcp-server/gateway_server.py:53-86` (a teljes
hívás-hely, az `await loop.run_in_executor(...)` belsejében a TÉNYLEGES,
importált `compile_context()` hívással):

```python
@mcp.tool()
async def get_gateway_context_pack(
    session_id: str, session_repo_root: str, max_chunks: int = 50
) -> dict[str, Any]:
    ...
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
```

Az import file:line: `mcp-server/gateway_server.py:47`:

```python
from gateway_core.compile_context import compile_context  # noqa: E402
```

## Real Postgres + Real Subprocess Proof

Új teszt: `tests/test_mcp_server/test_gateway_server.py` — a
`test_compile_context.py` `pg_config`/`seeded_session_id`/`session_repo_root`
fixture-mintáját KÖVETI (nem újra feltalálva), eggyel a hívási láncban feljebb:
valódi `mcp-server/gateway_server.py` subprocess + valódi stdio MCP handshake +
`get_gateway_context_pack` tool hívás → (belül) `compile_context()` → (belül) MÁSODIK
valódi `session_server.py` subprocess → valódi Postgres.

A `.venv-host` build (a `cic-mcp-gateway` klónban korábban nem létezett):

```
$ python3 -m venv .venv-host
$ .venv-host/bin/pip install --default-timeout=120 -r requirements.txt
...
Successfully installed ... mcp-1.28.0 ... psycopg-3.3.4 ... sentence-transformers-5.6.0 ... torch-2.12.1 ...
EXIT: 0
```

Baseline regresszió (a MÁR meglévő `compile_context()` teszt, a wiring ELŐTTI
bizonyíték, hogy az alap-réteg sértetlen):

```
$ .venv-host/bin/python -m pytest tests/test_gateway_core/test_compile_context.py -v --no-cov
tests/test_gateway_core/test_compile_context.py::test_compile_context_available_session_end_to_end PASSED [ 50%]
tests/test_gateway_core/test_compile_context.py::test_compile_context_unavailable_session_end_to_end PASSED [100%]
============================== 2 passed in 11.16s ==============================
```

Az ÚJ wiring-teszt TÉNYLEGES futása (env: `SESSION_STORE_PG_HOST=localhost`,
`SESSION_STORE_PG_PORT=55436`, `SESSION_STORE_PG_DB=testdb`,
`SESSION_STORE_PG_USER=postgres`, `SESSION_STORE_PG_PASSWORD=test`,
`SESSION_CONTEXT_PACK_TEST_SESSION_REPO=<cic-mcp-session klón>`):

```
$ .venv-host/bin/python -m pytest tests/test_mcp_server/test_gateway_server.py -v --no-cov
tests/test_mcp_server/test_gateway_server.py::test_get_gateway_context_pack_available_session_end_to_end PASSED [ 50%]
tests/test_mcp_server/test_gateway_server.py::test_get_gateway_context_pack_unavailable_session_end_to_end PASSED [100%]
============================== 2 passed in 10.85s ==============================
```

Kombinált futás (mindkét tesztfájl együtt, nincs interferencia):

```
$ .venv-host/bin/python -m pytest tests/test_gateway_core/ tests/test_mcp_server/ -v --no-cov
tests/test_gateway_core/test_compile_context.py::test_compile_context_available_session_end_to_end PASSED [ 25%]
tests/test_gateway_core/test_compile_context.py::test_compile_context_unavailable_session_end_to_end PASSED [ 50%]
tests/test_mcp_server/test_gateway_server.py::test_get_gateway_context_pack_available_session_end_to_end PASSED [ 75%]
tests/test_mcp_server/test_gateway_server.py::test_get_gateway_context_pack_unavailable_session_end_to_end PASSED [100%]
============================== 4 passed in 12.64s ==============================
```

A `:chunk:`-ref note tényleges megléte — egy önálló, a teszttel azonos pipeline-t
futtató kiegészítő ellenőrző script kimenete (ugyanazon `get_gateway_context_pack`
MCP tool hívás, ugyanazon `.venv-host` subprocess-en keresztül), a teljes
`session_derived_notes[]` tömb (NEM csak egy status-note):

```json
"session_derived_notes": [
  {
    "content": "Session 5132d656-cdca-4ba5-b1fa-52d91a49e485 status='open', started_at=2026-06-22T13:00:00Z, last_seen_at=2026-06-22T13:01:00Z, pending_jobs=0.",
    "trust": "session_derived",
    "ref": "session:5132d656-cdca-4ba5-b1fa-52d91a49e485:status"
  },
  {
    "content": "User: evidence print turn 1.",
    "trust": "session_derived",
    "ref": "session:5132d656-cdca-4ba5-b1fa-52d91a49e485:chunk:13"
  },
  {
    "content": "Assistant: evidence print turn 2.",
    "trust": "session_derived",
    "ref": "session:5132d656-cdca-4ba5-b1fa-52d91a49e485:chunk:14"
  }
]
```

Két `:chunk:`-ref note van jelen (`...:chunk:13`, `...:chunk:14`) a status-note mellett
— a `tests/test_mcp_server/test_gateway_server.py::test_get_gateway_context_pack_available_session_end_to_end`
teszt ugyanezt a `chunk_refs = [n for n in envelope["session_derived_notes"] if ":chunk:" in n["ref"]]; assert len(chunk_refs) >= 1`
asszerciót futtatja le minden futáskor (lásd a teszt forrását,
`tests/test_mcp_server/test_gateway_server.py` "Hardened assertion" blokk).

## Findings

- A `compile_context()` szinkron entry pointja (`asyncio.run()`) NEM kompatibilis
  egy már futó event loop-pal — ezt a FastMCP stdio tool-hívás biztosítja. Ezt a
  hidat a `gateway_server.py` oldalán kellett megépíteni (`run_in_executor`), NEM a
  `compile_context()` átírásával — ez konzisztens a "Nem cél" szekció "a
  `compile_context()` függvény módosítása" tiltásával.
- `git status --short` a `cic-mcp-gateway` klónban a job végén:
  ```
  ?? mcp-server/gateway_server.py
  ?? tests/test_mcp_server/
  ```
  — `mcp-server/server.py` NEM jelenik meg módosítottként, a generikus KB-szerver
  érintetlen.
- A `cic-mcp-gateway/CLAUDE.md` "Jelenlegi állapot" szekciója jelenleg azt állítja,
  hogy "nincs még gateway-specifikus implementáció" — ez az állítás ezzel a jobbal
  RÉSZBEN elavulttá vált: az "agent-facing context API" (`architecture.md`
  "cic-mcp-gateway" "Igen" lista) első konkrét megvalósítása létezik és futtatva
  bizonyított. A CLAUDE.md frissítése NEM része ennek a jobnak (nem volt "Required
  Output Files"/"Feladat" pont), de a következő jobban érdemes felülvizsgálni.
- A `.venv-host` 5.4 GB méretű lett a `torch`/`sentence-transformers`/CUDA
  dependency-lánc miatt (ugyanaz a méret-jelenség, amit
  `gateway-compile-context-test-hardening-001` "Findings" szekciója is dokumentált a
  `cic-mcp-session` oldalán) — ez gitignore-olt, nem kerül commitba.
- A `get_gateway_context_pack` tool csak a `session-context-recall` query_intent-et
  fedi (mert maga a `compile_context()` is csak ezt fedi, lásd
  `gateway_core/compile_context.py` modul docstring "Scope") — ez NEM ennek a jobnak
  a hiánya, hanem a mögötte hívott függvény jelenlegi, dokumentált scope-ja.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| Mindkét prerequisite (`session-context-pack-v1-001`, `gateway-compile-context-test-hardening-001`) `status: "done"` | proven | `jobs/index.yaml:107-110`, `jobs/index.yaml:29-32` idézve fent | grep kimenet idézve | low |
| ÚJ, KÜLÖN `mcp-server/gateway_server.py` modul létezik, saját `"cic-gateway"` FastMCP instance-szel | proven | `mcp-server/gateway_server.py:49` `mcp = FastMCP("cic-gateway")` | fájl tartalom idézve, `git status` mutatja új fájlként | low |
| `mcp-server/server.py` (generikus KB-szerver) NEM módosult | proven | `git status --short` kimenet: `mcp-server/server.py` nem jelenik meg | git status idézve | low |
| `get_gateway_context_pack` tool TÉNYLEGESEN hívja a `compile_context()`-et | proven | `mcp-server/gateway_server.py:47` import + `:53-86` hívás file:line idézve, ÉS a futtatott teszt bizonyítja a teljes láncot (lásd alábbi sor) | kód idézve + pytest futás | low |
| Valós subprocess + stdio MCP handshake + valós Postgres a TELJES láncon (MCP tool → compile_context() → session subprocess → Postgres) | proven | `tests/test_mcp_server/test_gateway_server.py::test_get_gateway_context_pack_available_session_end_to_end PASSED` (10.85s), envelope JSON idézve `:chunk:13`/`:chunk:14` ref-ekkel | tényleges pytest-futás kimenete idézve | low |
| A visszakapott envelope-ban van legalább egy `:chunk:`-ref note (nem csak status-note) | proven | JSON envelope idézve fent, 2 db `...:chunk:N` ref + a teszt saját `assert len(chunk_refs) >= 1` asszerciója zölden futott | pytest PASSED + envelope JSON idézve | low |
| Negatív eset (nem létező session_id) `proof_requirements[]`-en keresztül szivárog fel, nem silent-empty envelope-on | proven | `test_get_gateway_context_pack_unavailable_session_end_to_end PASSED` | pytest futás kimenete | low |
| `asyncio.run()` ütközés a FastMCP event loop-pal valós, nem hipotetikus hiba volt | proven | első tesztfutási kísérlet kimenete: `json.decoder.JSONDecodeError` + a tool hibaüzenete `"asyncio.run() cannot be called from a running event loop"` (reprodukálva, majd javítva `run_in_executor`-ral) | hibaüzenet idézve a job futása közben | low |
| Nincs valós, tartós production Postgres-instance | proven (negatív állítás) | a teszt egy disposable `pgvector/pgvector:pg16` containert (`gateway-wiring-test`) használ, env-ből konfigurálva, a riport sehol nem állít deployolt instance-t | env var lista + riport szövege | low |
| `compile_context()` saját kódja nem módosult | proven | a job "Nem cél" szekciója tiltja, és a klón `git status`/`git diff` a `gateway_core/` alatt nem mutat módosítást | git status | low |

## Decisions Proposed

- A `get_gateway_context_pack` tool `async def` + `run_in_executor` mintáját
  érdemes referenciaként megtartani minden további gateway-tool-nak, ami egy
  szinkron, `asyncio.run()`-t belül használó `gateway_core.*` függvényt hív MCP
  kontextusból — ez NEM `compile_context()`-specifikus probléma, bármely jövőbeli
  gateway_core függvény ugyanebbe a falba ütközne FastMCP alól hívva.
- `status_after_merge: candidate` indokolt: a call chain TÉNYLEGESEN
  futtatott és bizonyított, de a query_intent jelenleg egyetlen forrásra
  (`cic-mcp-session`) és egyetlen intent-re (`session-context-recall`) korlátozott —
  ez NEM hiba, hanem a mögöttes `compile_context()` jelenlegi, dokumentált scope-ja.

## Rejected / Out Of Scope

- `compile_context()` belső logikájának módosítása vagy reimplementálása — a job
  kizárólag a HÍVÓ oldalon (gateway_server.py) oldotta meg az event-loop ütközést.
- A `mcp-server/server.py` generikus KB-szerver bővítése az új tool-lal — KÜLÖN
  modul lett, a "Forbidden Shortcuts" tiltása szerint.
- `shared_memory_notes`/`cic-mcp-shared` bekötése — külön job tárgya (input.md "Nem
  cél").
- Valós, tartós production Postgres-instance felállítása/deployolása — a job
  kizárólag a disposable teszt-Postgres-en (`gateway-wiring-test` container)
  bizonyított.
- `cic-mcp-gateway/CLAUDE.md` "Jelenlegi állapot" szekciójának frissítése — nem volt
  "Required Output Files"/"Feladat" pont, jelölve "Findings"-ben mint nyitott
  follow-up.

## Risks

- A `get_gateway_context_pack` tool jelenleg NEM ad vissza explicit hibakódot, ha a
  `session_repo_root` paraméter érvénytelen útvonalra mutat (pl. nem létező
  `cic-mcp-session` checkout) — ez a mögöttes `compile_context()`/
  `SessionServerLaunchConfig` viselkedésétől függ (subprocess indítási hiba
  felszínre kerül-e MCP tool error-ként vagy elakad) — ezt ez a job NEM tesztelte
  explicit negatív esetként (csak a "session nem létezik" negatív esetet, ami a DB
  szintjén dől el, nem a repo_root szintjén).
- A `run_in_executor(None, ...)` az alapértelmezett `ThreadPoolExecutor`-t használja
  — sok egyidejű `get_gateway_context_pack` hívás esetén ennek mérete (alapértelmezett
  `min(32, os.cpu_count() + 4)`) korlátozhatja a párhuzamosságot; ez jelenleg NEM
  konfigurálható paraméterként a tool-on, és ez a job nem terhelés-tesztelte ezt a
  korlátot.
- A `.venv-host` 5.4 GB-os mérete (torch/CUDA dependency-lánc CPU-only
  sentence-transformers használathoz) ismert, dokumentált korlátozás — lásd
  `gateway-compile-context-test-hardening-001` saját "Risks" szekcióját, ugyanaz a
  jelenség itt is megjelenik a `cic-mcp-gateway` oldalán.

## Definition Of Done Check

- [x] mindkét prerequisite `id:` kulccsal megerősítve, GO/NO-GO döntés indokolva → GO,
      lásd "Prerequisite Check"
- [x] ÚJ `mcp-server/gateway_server.py`, KÜLÖN modulként (NEM a generikus KB-szerver
      módosítása), `compile_context()`-et TÉNYLEGESEN hívó tool-lal, file:line idézve
      → lásd "New Gateway MCP Server — Call Site"
- [x] valós, futtatott teszt: subprocess + stdio MCP handshake + valós Postgres,
      legalább egy `:chunk:`-ref note bizonyítva (nem csak status-note) → lásd "Real
      Postgres + Real Subprocess Proof"
- [x] claim-evidence tábla kitöltve, nem üres → lásd "Claim-Evidence Matrix"
- [x] a riport NEM állítja, hogy valós production Postgres-instance létezik → a
      "Real Postgres + Real Subprocess Proof" szekció explicit a disposable
      teszt-containert nevezi meg, "Rejected / Out Of Scope" is megerősíti

## Next Jobs

- `cic-mcp-gateway/CLAUDE.md` "Jelenlegi állapot" szekció frissítése, hogy tükrözze
  az ÚJ `mcp-server/gateway_server.py`/`get_gateway_context_pack` meglétét (jelenleg
  még "nincs még gateway-specifikus implementáció"-t állít).
- `get_gateway_context_pack` tool bővítése a `compile_context()` mögötti scope
  bővülésével párhuzamosan (pl. ha egy jövőbeli job a `query_intent`
  paraméterezhetőségét/más session_api tool-okat is bekötné a
  `compile_context()`-be, ezt a tool-t NEM kell módosítani, mert csak forward-olja a
  paramétereket — de ha a tool saját signature-je bővülne, azt külön jobban kell
  kezelni).
- A `session_repo_root` érvénytelen útvonal esetén történő hibakezelés explicit
  negatív teszttel lefedése (lásd "Risks").
