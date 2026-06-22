# gateway-session-adapter-contract-001 Output

## Scope

Ez a job az ELSŐ Phase 2 capability-job (`.cic-context/factory-docs/execution-phases.md`
"Phase 2 - Session + Gateway Integration": `gateway-session-adapter-contract-001` /
`factory-session-bridge-001` / `session-context-pack-v1-001` közül az első). A job
KONTRAKTUS-szinten definiálja, hogyan fordítaná a `cic-mcp-gateway` (jövőbeli) adaptere a
`cic-mcp-session` forrást egy `GatewayContextEnvelope`-ba — KIZÁRÓLAG a `cic-mcp-session`
TÉNYLEGES, regisztrált MCP tool-jain keresztül (`mcp-server/session_server.py`, 7 tool),
SOHA nem direkt SQL/tábla-hozzáféréssel. Ez nem implementáció: nincs Python adapter-kód,
nincs futtatott `compile_context` hívás, nincs schema-módosítás.

Nem cél (lásd input.md "Nem cél"): tényleges adapter-kód, a
`GatewayContextEnvelope`/source-registry schema módosítása, a `cic-mcp-session` repo
módosítása, és a Phase 2 másik két jobja (`factory-session-bridge-001`,
`session-context-pack-v1-001`).

## Inputs Read

- `cic-mcp-factory/.cic-context/factory-docs/execution-phases.md` — "Phase 2 - Session +
  Gateway Integration" szekció (65-87. sor) — NORMATÍV
- `cic-mcp-factory/.cic-context/factory-docs/architecture.md` — "Fő határok" szekció
  (31-89. sor), kiemelten `cic-mcp-session` Igen/Nem (33-54. sor) és `cic-mcp-gateway`
  Igen/Nem (56-72. sor)
- `cic-mcp-gateway/output/gateway-context-envelope.schema.yaml` — TELJESEN elolvasva, a
  `session_derived_notes[]` property (277-302. sor: `content`/`trust`/`ref` mezők, `trust`
  enum `["session_local", "session_derived"]`), valamint a teljes `required`/`properties`/
  `forbidden_combinations` szerkezet
- `cic-mcp-gateway/output/gateway-source-registry.schema.yaml` — TELJESEN elolvasva, a
  `cic-mcp-session` bejegyzés mezői (`source_id`, `trust_domain`, `owns_raw_storage`,
  `returns_trust_envelope`, `query_capabilities`, `canonical`)
- `cic-mcp-gateway/output/gateway-context-envelope-contract.md` — TELJESEN elolvasva, a
  "Separation From Source-Specific MCP APIs" szekció (330-357. sor) — ez a job ezt az elvet
  konkretizálja a tényleges `cic-mcp-session` tool-okra
- `cic-mcp-session/mcp-server/session_server.py` — TELJESEN elolvasva (457 sor), a 7
  `@mcp.tool()` regisztráció és minden docstring/SQL-hívás
- `cic-mcp-session/CLAUDE.md` — TELJESEN elolvasva, trust modell (32-40. sor:
  `canonical: false`, `promotion_allowed: false`, `interpreted: false`,
  `default_scope: session_id`, `cross_session: false`)
- `cic-mcp-session/output/session-source-refs-api-report.md` — `ref_kind` lehetséges
  értékei (`tool_call`/`file`/`url`) megerősítve
- `cic-mcp-session/session_store/chunk_indexer.py` — `ref_kind` konstansok (139-141. sor:
  `TOOL_CALL_ROLE = "tool"`, `FILE_PATH_KEYS = ("file_path", "path", "notebook_path")`)
  megerősítve, a `get_session_source_refs` `ref_kind` paraméterének értékkészletéhez
- `mcp__cic-graph__kb_status` (Boot sequence 1. lépés) — eredmény: mind a 6 KB artifact
  (`chunks.pkl`, `graph_nodes.pkl`, `graph_edges.pkl`, `inverted_index.pkl`, `faiss.index`,
  `bm25.pkl`) `exists: true`, `cache_info` 6 hit / 1 miss / 1 currsize — a KB friss és
  elérhető, a Boot sequence teljesítve

## Session MCP API Surface

GREP-bizonyíték a 7 tool tényleges `@mcp.tool()` regisztrációjára (teszt-fájlok
kizárva — a `mcp-server/session_server.py` nem tartalmaz `test_` mintát, ezért a
`grep -v test_` szűrő nem szűrt ki semmit ebből az egyetlen fájlból, de a job-spec által
előírt parancsot pontosan ahogy kérve futtattam):

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

Ez bizonyítja: mind a 7 függvény valódi, kliens-oldalról hívható MCP tool (a `@mcp.tool()`
dekorátor regisztrálja a `FastMCP("cic-session")` instance-hez, `session_server.py:91`), nem
csak belső Python segédfüggvény.

| Tool | file:line szignatúra | Visszatérési típus | SQL forrás (idézve a docstringből) |
|---|---|---|---|
| `search_session_context` | `mcp-server/session_server.py:95` `def search_session_context(session_id: str, query: str, limit: int = 20) -> list[dict]` | `list[dict]` kulcsok: `chunk_id`, `turn_id`, `text`, `fused_score` (139-146. sor) | `session_api.search_context_hybrid()` (hibrid FTS+vector, RRF-fúzió) |
| `search_session_context_fts` | `mcp-server/session_server.py:151` `def search_session_context_fts(session_id: str, query: str, limit: int = 20) -> list[dict]` | `list[dict]` kulcsok: `chunk_id`, `turn_id`, `text`, `rank` (188-195. sor) | `session_api.search_context()` (csak FTS) |
| `search_session_context_vector` | `mcp-server/session_server.py:200` `def search_session_context_vector(session_id: str, query: str, limit: int = 20) -> list[dict]` | `list[dict]` kulcsok: `chunk_id`, `turn_id`, `text`, `similarity` (247-254. sor) | `session_api.search_context_vector()` (csak cosine vector) |
| `get_session_timeline` | `mcp-server/session_server.py:259` `def get_session_timeline(session_id: str, limit: int = 100) -> list[dict]` | `list[dict]` kulcsok: `turn_id`, `occurred_at`, `role`, `turn_seq` (291-298. sor) | `session_api.get_timeline()` |
| `get_session_context_pack` | `mcp-server/session_server.py:303` `def get_session_context_pack(session_id: str, max_chunks: int = 50) -> list[dict]` | `list[dict]` kulcsok: `chunk_id`, `turn_seq`, `text` (338-344. sor) | `session_api.get_context_pack()` |
| `get_session_status` | `mcp-server/session_server.py:349` `def get_session_status(session_id: str) -> dict` | `dict` kulcsok: `session_id`, `status`, `started_at`, `last_seen_at`, `pending_jobs`; **vagy `{}` ha nincs ilyen session** (367-371. sor docstring, 383-384. sor: `if row is None: return {}`) | `session_api.session_status()` |
| `get_session_source_refs` | `mcp-server/session_server.py:396` `def get_session_source_refs(session_id: str, ref_kind: str \| None = None, limit: int = 100) -> list[dict]` | `list[dict]` kulcsok: `source_ref_id`, `chunk_id`, `turn_id`, `ref_kind`, `ref_value`, `content_hash` (439-447. sor); `ref_kind` ∈ `{"tool_call", "file", "url"}` (`session_store/chunk_indexer.py:139-141`) | `session_api.get_source_refs()` |

## Adapter Input/Output Contract

Az adapter (jövőbeli implementáció, NEM ez a job) a `GatewayContextEnvelope` compile-time
fázisában, `scope.scope_kind == "session"` esetén, a `scope.session_id` mezőből venné a
`cic-mcp-session` MCP tool-hívások `session_id` paraméterét. A kontraktus 3 tool-osztályt
különböztet meg:

### 1. Státusz-ellenőrzés — minden compile_context hívás ELSŐ session-lépése

- **Tool**: `get_session_status(session_id)` — `mcp-server/session_server.py:349`
- **Adapter-hívás**: `get_session_status(session_id=scope.session_id)`
- **Cél**: megállapítani, hogy a session létezik-e, MIELŐTT bármilyen content-tool-t
  hívna — ld. "Unavailable-Session Behavior" szekció.
- **Fordítás**: ha a visszatérő `dict` NEM üres, a `status`/`started_at`/`last_seen_at`/
  `pending_jobs` mezőkből EGY `session_derived_notes[]` bejegyzés készül (összegző
  szöveg), `ref` egy `refs[]`-be felvett `session:<session_id>:status` lokátorra mutat.

### 2. Tartalom-lekérés — a query_intent szerint route-olt tool

A `query_intent` dönti el, melyik content-tool fut (a gateway saját routing-felelőssége,
`architecture.md` "Fő határok" `cic-mcp-gateway` Igen-lista "query intent felismerés"
pontja — ez NEM ennek a jobnak a feladata, csak a leképezést rögzíti):

| `query_intent` minta | Hívott tool | Paraméterek | Fordítás `session_derived_notes[]`-be |
|---|---|---|---|
| `"session-history-recall"` | `get_session_timeline(session_id, limit)` — `mcp-server/session_server.py:259` | `session_id=scope.session_id`, `limit` az adapter konfigurációjából (alapérték a tool-default, 100) | minden timeline-sorból (`turn_id`, `occurred_at`, `role`, `turn_seq`) egy `session_derived_notes[]` bejegyzés, `content` = a sor szöveges összefoglalása, `ref` = `session:<session_id>:turn:<turn_id>` |
| `"session-context-recall"` (alap context pack lekérés) | `get_session_context_pack(session_id, max_chunks)` — `mcp-server/session_server.py:303` | `session_id=scope.session_id`, `max_chunks` az adapter konfigurációjából (alapérték a tool-default, 50) | minden `{chunk_id, turn_seq, text}` sorból egy `session_derived_notes[]` bejegyzés, `content` = `text`, `ref` = `session:<session_id>:chunk:<chunk_id>` |
| `"session-search"` / explicit keresési query | `search_session_context(session_id, query, limit)` — `mcp-server/session_server.py:95` (hibrid alapeset) | `session_id=scope.session_id`, `query` = az agent kérdés szövege, `limit` az adapter konfigurációjából | minden `{chunk_id, turn_id, text, fused_score}` sorból egy `session_derived_notes[]` bejegyzés, `content` = `text`, `ref` = `session:<session_id>:chunk:<chunk_id>` (a `fused_score` NEM kerül a `content`/`ref` mezőbe — a gateway saját `trust_summary.per_category.session_derived_notes` aggregálja a megbízhatóságot, nem a forrás raw score-ja) |
| (opcionális, finomhangolt search) `"session-search-fts"` / `"session-search-vector"` | `search_session_context_fts(...)` — `:151` / `search_session_context_vector(...)` — `:200` | ugyanaz a paraméterezés, mint `search_session_context`-nél | ugyanaz a fordítás, mint a hibrid esetnél (`rank` ill. `similarity` is a forrás raw score-ja, nem kerül a `content`-be) |
| (provenance/proof igény) | `get_session_source_refs(session_id, ref_kind, limit)` — `mcp-server/session_server.py:396` | `session_id=scope.session_id`, `ref_kind` ∈ `{"tool_call", "file", "url", None}`, `limit` az adapter konfigurációjából | NEM `session_derived_notes[]`-be megy — ez a `refs[]` tömb feltöltésére szolgál: minden `{source_ref_id, chunk_id, turn_id, ref_kind, ref_value, content_hash}` sorból egy `refs[]` bejegyzés (`ref_id` = `session:<session_id>:source_ref:<source_ref_id>`, `excerpt` = `ref_value`), amelyre a `session_derived_notes[].ref` mezők hivatkozhatnak provenance-bizonyítékként |

**Fontos megkötés**: az adapter EGY `compile_context` híváson belül NEM hívja
egyszerre a `search_session_context`/`search_session_context_fts`/
`search_session_context_vector` mindhárom variánsát ("search_all" jellegű shortcut) — a
`query_intent`-routing pontosan egyet választ; ez ugyanaz az elv, mint a
`gateway-context-envelope-contract.md` `gateway-route-query-not-search-all` invariánsa,
csak a `cic-mcp-session` tool-választás szintjén megismételve.

## Trust Mapping

A `cic-mcp-session/CLAUDE.md` trust modellje (32-40. sor):

```yaml
canonical: false
promotion_allowed: false
interpreted: false   # ingress/raw szinten
default_scope: session_id
cross_session: false
```

A `gateway-context-envelope.schema.yaml` `session_derived_notes[].trust` enuma pontosan
`["session_local", "session_derived"]` (286-293. sor). Döntés — melyik tool-válasz melyik
trust-értéket kapja:

| Tool | `trust` érték | Indoklás |
|---|---|---|
| `search_session_context` (hibrid), `search_session_context_fts`, `search_session_context_vector` | `session_local` | A visszaadott `text` mező a chunk EREDETI, nyers szövege (`session_store/chunk_indexer.py` chunk-tartalma), csak a *keresési sorrend* (rank/similarity/fused_score) a transzformáció — a tartalom maga nem aggregált, nem projektált, közvetlenül egy `session_core.chunks` sor szövege. Ez megfelel az "ingress/raw szinten interpreted: false" elvnek: a chunk-szöveg semantikailag nincs átalakítva, csak relevancia szerint rendezve. |
| `get_session_context_pack` | `session_derived` | A `session_api.get_context_pack()` egy ALÁBONTOTT, `(turn_seq, chunk_seq)` szerint ÖSSZEÁLLÍTOTT, session-szintű projekciót ad vissza — ez már egy AGGREGÁLT nézet a `chunks` tábla felett (nem egyetlen, izolált keresési hit, hanem egy session-szintű "context pack" összeállítás), tehát egy szinttel feljebb van a nyers chunk-tól. Ez konzisztens a `turn_projector`/`chunk_indexer` worker-lánc (CLAUDE.md "Jelenlegi állapot") feldolgozási rétegével, amely már nem ingress-szintű, hanem derivált adat. |
| `get_session_timeline` | `session_local` | A timeline sorai (`turn_id`, `occurred_at`, `role`, `turn_seq`) a raw turn-projekció KÖZVETLEN, nem aggregált felsorolása — egy turn = egy esemény, nincs összegzés/szűrés a tartalmon, csak kronologikus rendezés. |
| `get_session_status` (ha a session létezik) | `session_derived` | A `status`/`pending_jobs` egy AGGREGÁLT állapot-összegzés (a `session_api.session_status()` `pending_jobs BIGINT` egy COUNT-jellegű derivált érték, nem egyetlen sor másolata) — ez derivált metaadat, nem nyers esemény-szöveg. |
| `get_session_source_refs` | N/A — ez NEM `session_derived_notes[]`-be megy, hanem `refs[]`-be; a `refs[]` schema-eleme nem tartalmaz `trust` mezőt (`gateway-context-envelope.schema.yaml` 430-450. sor: `refs[].properties` csak `ref_id`/`source_id`/`excerpt`) | A provenance-referenciák a bizonyíték-táblába (evidence table) kerülnek, nem trust-jelölt tartalmi mezőbe — a `trust` fogalma itt nem releváns, mert a `refs[]` sosem önállóan jelenik meg tartalmi állításként, csak más mezők hivatkozási célpontjaként. |

**Általános szabály**: nyers, egyedi chunk-szöveg (egyetlen keresési hit vagy egyetlen
timeline-esemény) → `session_local`; több sorból összeállított/aggregált/számított nézet
(context pack összeállítás, status-összegzés `pending_jobs` count-tal) → `session_derived`.
Ez a határ nem önkényes: a `session_api.*` SQL-réteg maga is két csoportra esik —
"egy táblát egy szűrővel olvas" (`search_context*`, `get_timeline`) vs. "több sort
összeállít egy derivált nézetté" (`get_context_pack` `turn_seq`/`chunk_seq` szerinti
összeállítás, `session_status` `pending_jobs` COUNT-aggregátum).

## Unavailable-Session Behavior

A `get_session_status(session_id)` dokumentált viselkedése
(`mcp-server/session_server.py:367-371` docstring, megerősítve a tényleges
implementáció `:383-384` sorával):

```
mcp-server/session_server.py:367:        dict with keys session_id (str), status (str), started_at
mcp-server/session_server.py:368:        (datetime), last_seen_at (datetime), pending_jobs (int). Returns an
mcp-server/session_server.py:369:        empty dict if no matching session_core.sessions row exists (the SQL
mcp-server/session_server.py:370:        function itself returns zero rows in that case — no Python-side
mcp-server/session_server.py:371:        existence check is added here, same "let the SQL function's own
mcp-server/session_server.py:372:        cardinality decide" stance as the other wrappers in this module).
```

```
mcp-server/session_server.py:383:    if row is None:
mcp-server/session_server.py:384:        return {}
```

**Döntés**: az adapter `proof_requirements[]` mezőn keresztül jelzi explicit a "session nem
elérhető" esetet, NEM `conflicts[]`-en.

**Indoklás**: a `conflicts[]` schema-leírása (`gateway-context-envelope.schema.yaml`
377-404. sor) "disagreement between sources" — legalább KÉT, egymásnak ellentmondó
`conflicting_refs` bejegyzést követel (`minItems: 2`). Egy nem létező session esetén
NINCS két forrás, ami ellentmondana egymásnak — egyetlen forrás (`cic-mcp-session`) adott
egy negatív/üres választ. Ez nem KONFLIKTUS, hanem egy VERIFIKÁCIÓS HIÁNY: "ezt nem tudtuk
megerősíteni, mert a forrás nem talált session-t ehhez az ID-hez." A
`proof_requirements[]` schema-leírása (406-426. sor) pontosan ezt fedi: "What must still
be verified before this content can be treated as canonical truth" — ez illik a "a
session_id-t nem lehetett feloldani, az adapter nem tudja megerősíteni vagy elvetni a
kért session-scope-ot" állításra.

**Konkrét kontraktus**: ha `get_session_status(session_id)` `{}`-t ad vissza, az adapter:
1. NEM hív semmilyen további content-tool-t ugyanarra a `session_id`-re (a státusz-
   ellenőrzés a `compile_context` ELSŐ session-lépése — lásd "Adapter Input/Output
   Contract" 1. pont — éppen azért, hogy ezt a forbidden shortcut-ot megelőzze: "néma,
   de sikeresnek tűnő envelope" szimulálása egy nem létező session-ből).
2. `sources_used[]`-ba FELVESZI a `cic-mcp-session` bejegyzést (`trust_domain:
   "session_local"`, `query_capability_used` nincs megadva, mert csak a státusz-
   ellenőrzés futott le, content-lekérés nem) — a forrás MEGKÉRDEZÉSRE került, csak
   negatív választ adott; ezt is rögzíteni kell, nem szabad kihagyni a `sources_used[]`-
   ból, mert az "nem is kérdeztük meg" állítás lenne, ami hamis.
3. `session_derived_notes[]` ÜRES marad ehhez a session-hez (nincs tartalom, amit
   becsomagolni).
4. `proof_requirements[]`-be EGY bejegyzés kerül: `description`: "A kért session_id
   (<session_id>) nem feloldható a cic-mcp-session rétegben — get_session_status() üres
   eredményt adott, tehát a session_core.sessions táblában nincs ehhez az ID-hez tartozó
   sor (vagy törölve lett, vagy soha nem létezett, vagy elgépelt ID). A session-scope-ú
   tartalom emiatt nem kompilálható, amíg ez nem tisztázódik."; `blocking_for`: a session-
   scope-ú content-mezőkre utaló placeholder ref (lásd "Example — Session Unavailable").
5. `trust_summary.per_category.session_derived_notes` = `"unverified"` (NEM `"not_used"`
   — mert itt nem arról van szó, hogy a kategória nem volt releváns a query-hez, hanem
   hogy releváns volt, csak nem sikerült feloldani; `"not_used"` hamis állítást tenne
   arról, hogy a gateway egyáltalán nem próbálta a session-forrást használni).

Ez pontosan kizárja a Forbidden Shortcuts harmadik tételét ("a 'session nem elérhető'
eset néma elsiklása — üres, de 'sikeresnek' tűnő envelope"): az envelope explicit,
nem-üres `proof_requirements[]`-szel jelzi a hiányt, és a `trust_summary` sem state-eli
hamisan `"not_used"`-ot.

## Findings

1. A `gateway-context-envelope-contract.md` (a megelőző Phase 1B job riportja) már
   EXPLICIT módon utalt erre a jobra a "Separation From Source-Specific MCP APIs"
   szekcióban (352-356. sor): "azt a (jövőbeli) `gateway-session-adapter-contract-001` job
   adaptere konzumálja" — ez a job pontosan ezt a megelőző jobban megnevezett hidat zárja
   le kontraktus-szinten.
2. A `cic-mcp-session/mcp-server/session_server.py` docstringje (76-80. sor) explicit
   kimondja: "This module has NO production caller... no orchestrator/gateway wiring" —
   tehát a 7 tool jelenleg `implemented` (kódban él, MCP-regisztrált), de a
   `cic-mcp-gateway`-hez vezető híd `scaffold` szintű: nincs éles bekötés, csak ez a
   kontraktus-job formalizálja az ELVÁRT fordítást. A háromszintű státusz ennek a hídnak:
   `concept` (a `GatewayContextEnvelope.session_derived_notes[]` mező) → `code` (a 7
   `@mcp.tool()` függvény implementálva) → **runtime híd hiányzik** (nincs adapter-kód,
   nincs `.mcp.json` bekötés a gateway oldaláról a session szerverhez).
3. A `get_session_status` `{}` visszatérési értéke STRUKTURÁLISAN nem különbözteti meg
   "session nem létezik" és "session létezik, de minden mező NULL" eseteket — mindkettő
   `row is None` lenne csak az első esetben (a SQL function 0 sort ad vissza, ha nincs
   egyező `session_id`); ha LENNE egy session sor csupa NULL mezővel, az `row` NEM lenne
   `None`, és a dict NEM lenne üres (csak a mezői lennének `None` értékűek). Tehát az `{}`
   válasz EGYÉRTELMŰEN "nincs ilyen `session_id`" jelentésű, nem ambivalens — ez megerősíti,
   hogy a `proof_requirements[]` döntés helyes alapon áll.
4. A `search_session_context`/`search_session_context_fts`/`search_session_context_vector`
   három, külön regisztrált tool közötti választás (nem egyetlen paraméterezhető tool) azt
   jelenti, hogy az adapternek a `query_capability_used` mezőbe (`sources_used[].
  query_capability_used`, `gateway-context-envelope.schema.yaml` 209-216. sor) explicit be
  kell írnia, melyik variánst hívta (pl. `"hybrid"`/`"fts"`/`"vector"`) — ez a mező jelenleg
  szabad string, nincs hozzá enum a `gateway-source-registry.schema.yaml`
  `query_capabilities` listájában rögzítve a `cic-mcp-session` bejegyzésnél (ezt a klónozott
  registry-fájl jelenlegi tartalma alapján NEM tudtam ellenőrizni — lásd "Risks").
5. A `get_session_source_refs` az EGYETLEN a 7 tool közül, amely NEM `session_derived_notes[]`
   célmezőbe fordítódik, hanem a `refs[]` evidence-táblába — ezt a job-spec nem nevezte meg
   explicit célmezőként, de a "Feladat" 1. pontja ("refs[] bejegyzésekre" fordítás) ezt is
   lefedi; ezt a riport "Adapter Input/Output Contract" táblájában explicit jelöltem.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| Mind a 7 `cic-mcp-session` tool valódi, kliens-oldalról hívható `@mcp.tool()` regisztráció | proven | `grep -rn "@mcp.tool()" -A 1 mcp-server/session_server.py \| grep -v test_` kimenete (lásd "Session MCP API Surface"), 7 találat, mindegyik `def`-fel párosítva | parancs futtatva, kimenet szó szerint idézve | low |
| `search_session_context(session_id, query, limit=20)` szignatúra | proven | `mcp-server/session_server.py:95` idézve | fájl-tartalom idézve | low |
| `search_session_context_fts(session_id, query, limit=20)` szignatúra | proven | `mcp-server/session_server.py:151` idézve | fájl-tartalom idézve | low |
| `search_session_context_vector(session_id, query, limit=20)` szignatúra | proven | `mcp-server/session_server.py:200` idézve | fájl-tartalom idézve | low |
| `get_session_timeline(session_id, limit=100)` szignatúra | proven | `mcp-server/session_server.py:259` idézve | fájl-tartalom idézve | low |
| `get_session_context_pack(session_id, max_chunks=50)` szignatúra | proven | `mcp-server/session_server.py:303` idézve | fájl-tartalom idézve | low |
| `get_session_status(session_id)` szignatúra ÉS `{}` visszatérés nem létező session esetén | proven | `mcp-server/session_server.py:349` szignatúra + `:383-384` (`if row is None: return {}`) idézve | fájl-tartalom idézve | low |
| `get_session_source_refs(session_id, ref_kind=None, limit=100)` szignatúra | proven | `mcp-server/session_server.py:396-398` idézve | fájl-tartalom idézve | low |
| `ref_kind` paraméter értékkészlete `{"tool_call", "file", "url"}` | proven | `cic-mcp-session/session_store/chunk_indexer.py:139-141` (`TOOL_CALL_ROLE = "tool"`, `FILE_PATH_KEYS = (...)`) + `output/session-source-refs-api-report.md` "Inputs Read" szakasz idézve | fájl-tartalom idézve két helyről | low |
| A `session_derived_notes[].trust` enum pontosan `["session_local", "session_derived"]`, megegyezik a `cic-mcp-session` trust-szótárával | proven | `gateway-context-envelope.schema.yaml:286-293` + `cic-mcp-session/CLAUDE.md:32-40` idézve | fájl-tartalom idézve mindkét repóból | low |
| `session_local` vs `session_derived` döntés minden 5 content-tool-ra (nem `get_session_source_refs`-re, mert az nem ide megy) | partial | "Trust Mapping" tábla — DÖNTÉS, nem a forrás explicit dokumentálja a trust-szintet tool-szinten, ez a job saját, indokolt besorolása | döntés-indoklás idézve a riportban, nem külső forrásból bizonyított tény | medium — jövőbeli adapter-implementáció felülbírálhatja, ha a `cic-mcp-session` később explicit trust-mezőt ad vissza tool-szinten |
| `get_session_status(session_id)` `{}}`-t ad vissza, ha a session nem létezik | proven | `mcp-server/session_server.py:367-371` docstring + `:383-384` implementáció idézve | fájl-tartalom idézve | low |
| "Session nem elérhető" eset `proof_requirements[]`-en keresztül jelzendő, nem `conflicts[]`-en | proven (döntés, indoklással) | `gateway-context-envelope.schema.yaml:377-426` (`conflicts` vs `proof_requirements` leírás) idézve + indoklás "Unavailable-Session Behavior" szekcióban | schema-szöveg idézve + döntési érvelés | low |
| 2 teljes példa-envelope készült (elérhető + nem elérhető session eset) | proven | lásd "Example compile_context Response" két szekció lent | jelen dokumentum tartalma | low |
| A `get_session_source_refs` válasz a `refs[]` mezőbe fordítódik, NEM `session_derived_notes[]`-be | proven (döntés) | "Adapter Input/Output Contract" tábla utolsó sora + `gateway-context-envelope.schema.yaml:430-450` (`refs[]` schema, nincs `trust` mező) idézve | fájl-tartalom idézve + döntési érvelés | low |
| Az adapter EGY `compile_context` hívásban nem hívja a 3 search-variánst egyszerre ("search_all" elkerülése) | proven (döntés, kontraktus-szabály) | "Adapter Input/Output Contract" "Fontos megkötés" bekezdés + `gateway-context-envelope-contract.md` `gateway-route-query-not-search-all` invariáns idézve | schema-szöveg idézve + döntési érvelés | low |

## Example compile_context Response — Session Available

```yaml
apiVersion: "cic.gateway/v1"
kind: "GatewayContextEnvelope"
envelope_id: "a1b2c3d4-e5f6-4789-9abc-def012345678"
created_at: "2026-06-22T14:30:00Z"
query_intent: "session-history-recall"
scope:
  scope_kind: "session"
  session_id: "3f9a2b10-7c44-4e1a-9d2e-88a1c4f0b7e2"
answer_type: "history_recall"
sources_used:
  - source_id: "cic-mcp-session"
    trust_domain: "session_local"
    query_capability_used: "timeline"
trust_summary:
  overall_confidence: "medium"
  per_category:
    canonical_facts: "not_used"
    workdir_facts: "not_used"
    session_derived_notes: "medium"
    shared_memory_notes: "not_used"
canonical_facts: []
workdir_facts: []
session_derived_notes:
  - content: "Turn 14 (role=user, occurred_at=2026-06-22T09:02:11Z): user asked for the gateway-session-adapter-contract-001 job scope to be re-confirmed before implementation starts."
    trust: "session_local"
    ref: "ref-201"
  - content: "Turn 15 (role=assistant, occurred_at=2026-06-22T09:03:47Z): assistant confirmed scope is contract-only, no adapter code in this job."
    trust: "session_local"
    ref: "ref-202"
shared_memory_notes: []
conflicts: []
proof_requirements: []
refs:
  - ref_id: "ref-201"
    source_id: "cic-mcp-session"
    excerpt: "session:3f9a2b10-7c44-4e1a-9d2e-88a1c4f0b7e2:turn:14"
  - ref_id: "ref-202"
    source_id: "cic-mcp-session"
    excerpt: "session:3f9a2b10-7c44-4e1a-9d2e-88a1c4f0b7e2:turn:15"
```

**Adapter-hívás emögött**: 1) `get_session_status(session_id="3f9a2b10-...")` →
nem-üres dict (session létezik) → 2) `query_intent == "session-history-recall"` alapján
`get_session_timeline(session_id="3f9a2b10-...", limit=100)` →
`mcp-server/session_server.py:259` → két timeline-sor fordítva
`session_derived_notes[]`-be, `trust: "session_local"` (lásd "Trust Mapping": timeline =
nyers, nem-aggregált turn-felsorolás).

## Example compile_context Response — Session Unavailable

```yaml
apiVersion: "cic.gateway/v1"
kind: "GatewayContextEnvelope"
envelope_id: "b2c3d4e5-f607-489a-bcde-f01234567890"
created_at: "2026-06-22T15:05:22Z"
query_intent: "session-history-recall"
scope:
  scope_kind: "session"
  session_id: "00000000-0000-0000-0000-000000000000"
answer_type: "status_summary"
sources_used:
  - source_id: "cic-mcp-session"
    trust_domain: "session_local"
canonical_facts: []
workdir_facts: []
session_derived_notes: []
shared_memory_notes: []
trust_summary:
  overall_confidence: "unverified"
  per_category:
    canonical_facts: "not_used"
    workdir_facts: "not_used"
    session_derived_notes: "unverified"
    shared_memory_notes: "not_used"
conflicts: []
proof_requirements:
  - description: "A kért session_id (00000000-0000-0000-0000-000000000000) nem feloldható a cic-mcp-session rétegben — get_session_status() üres eredményt adott (mcp-server/session_server.py:383-384: 'if row is None: return {}'), tehát a session_core.sessions táblában nincs ehhez az ID-hez tartozó sor. A session-scope-ú tartalom emiatt nem kompilálható, amíg ez nem tisztázódik (törölt session, soha nem létezett, vagy elgépelt ID)."
    blocking_for: ["scope.session_id:00000000-0000-0000-0000-000000000000"]
refs: []
```

**Adapter-hívás emögött**: `get_session_status(session_id="00000000-...")` →
`mcp-server/session_server.py:349` → `{}` (üres dict, mert `row is None`) → az adapter
NEM hív további content-tool-t ugyanarra a `session_id`-re → `proof_requirements[]`-be
egy explicit bejegyzés, `sources_used[]` rögzíti, hogy a `cic-mcp-session` forrást
megkérdezte (csak negatív választ kapott), `trust_summary.per_category.
session_derived_notes` = `"unverified"` (nem `"not_used"` — lásd "Unavailable-Session
Behavior" 5. pont indoklása). `refs: []` jogos itt, mert nincs felbontható
provenance-locator — a `blocking_for` egy scope-szintű placeholder-stringre mutat, nem egy
`refs[]`-beli `ref_id`-re (a schema `blocking_for` mezője `type: array, items: string`,
nem korlátozza kizárólag `refs[].ref_id`-re — `gateway-context-envelope.schema.yaml:416-420`).

## Decisions Proposed

1. **A `get_session_status(session_id)` hívás MINDIG az adapter ELSŐ session-lépése** egy
   `compile_context` hívásban, mielőtt bármilyen content-tool futna — ez a kontraktus
   garantálja, hogy a "session nem elérhető" eset sosem csendben siklik el egy később
   meghívott content-tool 0-sornyi válasza mögött (pl. `get_session_context_pack` is
   visszaadhat üres listát, de ABBÓL nem derülne ki, hogy a session nem létezik vagy
   csak üres). Javaslat: a jövőbeli adapter-implementáció (`session-context-pack-v1-001`
   vagy egy külön implementációs job) ezt a sorrendet kötelezőként vegye át.
2. **`get_session_source_refs` válasza kizárólag `refs[]`-be fordítódik**, nem
   `session_derived_notes[]`-be — ez strukturálisan elkülöníti a "tartalmi állítás" és a
   "provenance-bizonyíték" szerepkört, ahogy a `GatewayContextEnvelope` schema egésze is
   elkülöníti a content-mezőket a `refs[]` evidence-táblától.
3. **Trust mapping szabály**: nyers/egyedi sor → `session_local`; több sorból
   összeállított/aggregált derivált nézet → `session_derived` (lásd "Trust Mapping" tábla
   és az utána következő "Általános szabály" bekezdés). Javaslat: a jövőbeli
   implementációs job vegye át ezt a két kategóriát ahelyett, hogy tool-onként újra
   eldöntené.
4. **"Session nem elérhető" → `proof_requirements[]`, NEM `conflicts[]`** — indoklás:
   "Unavailable-Session Behavior" szekció. Javaslat: ez legyen a normatív minta minden
   jövőbeli forrás-adapter (`cic-mcp-shared`, `cic-mcp-workdir`) hasonló "forrás nem
   található" esetére is, hacsak az adott forrás explicit nem indokolja a `conflicts[]`
   használatát (pl. ha VAN egy másik forrás, amely ellentmond).
5. **A `query_capability_used` mezőbe írandó értékek**: `"timeline"` (`get_session_timeline`),
   `"context_pack"` (`get_session_context_pack`), `"hybrid"`/`"fts"`/`"vector"` (a 3 search
   variáns), `"status"` (`get_session_status`), `"source_refs"` (`get_session_source_refs`)
   — javaslat: a `gateway-source-registry-contract-001` job (vagy egy patch-job) vegye fel
   ezt a 6 értéket a `cic-mcp-session` registry-bejegyzés `query_capabilities[]` listájába
   explicit, hogy a "Risks" szekcióban jelzett nyitott kérdés ne maradjon dokumentálatlan.

## Rejected / Out Of Scope

- **Tényleges adapter-kód (Python/MCP client) implementálása** — explicit kizárva
  (input.md "Nem cél" 1. pont); ez egy jövőbeli implementációs jobnak (pl.
  `session-context-pack-v1-001` vagy egy külön `gateway-session-adapter-impl-001`) való.
- **`GatewayContextEnvelope`/source-registry schema módosítása** — nem történt; a job
  során NEM találtam olyan hiányt, amely a schema MÓDOSÍTÁSÁT indokolná (a
  `session_derived_notes[].trust` enum már pontosan a két szükséges értéket tartalmazza,
  a `refs[]` schema már alkalmas a `get_session_source_refs` fordítására) — egyetlen
  KISEBB nyitott kérdés a `query_capabilities[]` enum-felsorolás hiánya a
  `gateway-source-registry.schema.yaml` `cic-mcp-session`-specifikus tartalmában, ezt a
  "Findings" 4. pontban és a "Risks" szekcióban jeleztem, NEM módosítottam csendben.
- **`cic-mcp-session` repo módosítása** — nem történt, a klón KIZÁRÓLAG olvasásra volt
  használva; semmilyen fájl nem lett írva/commitolva ebben a klónban.
- **`factory-session-bridge-001` / `session-context-pack-v1-001`** — a Phase 2 másik két
  jobja, explicit kizárva ebből a jobból (input.md "Nem cél" 4. pont).
- **Direkt SQL/tábla-hozzáférés bármilyen formában** — az egész kontraktus a 7 MCP tool-on
  keresztül modellez minden hozzáférést; nincs a riportban olyan javaslat, amely a
  `session_api.*` SQL-függvényeket vagy a `session_core.*`/`session_idx.*` táblákat direktben
  hívná meg a gateway oldaláról.

## Risks

- **`query_capability_used` enum-hiány kockázat**: a `gateway-context-envelope.schema.yaml`
  `sources_used[].query_capability_used` mező jelenleg szabad string (nincs enum), és a
  klónozott `gateway-source-registry.schema.yaml` `cic-mcp-session`-specifikus
  `query_capabilities[]` ÉRTÉKEI (a tényleges registry-ADAT, nem a schema maga) nem
  voltak része ennek a jobnak a forrás-listájának (a job csak a registry SCHEMA-fájlt
  kapta forrásként, nem egy konkrét, betöltött `cic-mcp-session` registry-bejegyzést) —
  emiatt nem tudtam ellenőrizni, hogy a "Decisions Proposed" 5. pontban javasolt 6 érték
  (`timeline`/`context_pack`/`hybrid`/`fts`/`vector`/`status`/`source_refs`) szinkronban
  van-e egy már létező, betöltött registry-bejegyzéssel. Mitigáció: a "Next Jobs"
  szekcióban jelzem, hogy egy követő job ellenőrizze/szinkronizálja ezt.
- **Trust mapping döntés nem külső forrásból bizonyított tény, hanem ennek a jobnak a
  indokolt besorolása** ("Trust Mapping" szekció, Claim-Evidence Matrix "partial" sora) —
  a `cic-mcp-session` jelenleg NEM ad vissza explicit trust-mezőt tool-szinten (a 7 tool
  válasza nem tartalmaz `trust`/`session_local`/`session_derived` kulcsot semelyik
  visszatérési dict-ben) — ez a job KÖVETKEZTETÉS a `CLAUDE.md` trust-modell és az
  egyes SQL-függvények aggregáltsági szintje alapján, nem egy a forrásban már meglévő,
  explicit jelölés idézése. Mitigáció: ha egy jövőbeli `cic-mcp-session` job explicit
  trust-mezőt ad a tool-válaszokhoz, az FELÜLÍRJA ezt a következtetés-alapú besorolást.
- **A `get_session_status` `{}` válasz kétértelműségének elméleti határa**: ha valaha egy
  `session_core.sessions` sor csupa NULL mezővel létezne, a tool NEM `{}`-t adna vissza
  (mert `row is None` csak akkor igaz, ha tényleg 0 sor van) — ez a job ezt a
  pereset-kockázatot a "Findings" 3. pontban dokumentálta, de nem tesztelte élesben
  (nincs DB-hozzáférés ehhez a jobhoz, csak a Python forráskód olvasása).
- **Az adapter implementáció hűsége ehhez a kontraktushoz**: ez a riport NEM futtatható
  validátor, csak dokumentált elvárás — egy jövőbeli implementáció technikailag
  eltérhet ettől anélkül, hogy ez a fájl elbukna (ahogy a `gateway-context-envelope-
  contract.md` "Risks" szekciója is hasonló kockázatot jelzett a saját
  `forbidden_combinations`-szabályaira).

## Definition Of Done Check

- [x] minden felhasznált session MCP tool-hoz `file:line` szignatúra idézve
      → mind a 7 tool, "Session MCP API Surface" tábla + "Adapter Input/Output Contract"
      tábla, mindegyik `mcp-server/session_server.py:<line>` idézettel
- [x] trust mapping (`session_local`/`session_derived`) definiálva, indoklással
      → "Trust Mapping" szekció, tool-onkénti tábla + "Általános szabály" bekezdés
- [x] "session nem elérhető" eset definiálva (`conflicts`/`proof_requirements` mezőn
      keresztül)
      → "Unavailable-Session Behavior" szekció, `proof_requirements[]` választva,
      indoklással (`conflicts[]` `minItems: 2` követelménye nem illik ide)
- [x] 2 teljes példa-envelope (elérhető + nem elérhető session eset)
      → "Example compile_context Response — Session Available" (2
      `session_derived_notes[]` bejegyzéssel) + "...— Session Unavailable"
- [x] claim-evidence tábla kitöltve, nem üres
      → 15 sor, mind `proven` vagy "proven (döntés)" státusszal, egy `partial` sorral
      explicit jelölve, hol van a döntés vs. bizonyított tény határa

## Next Jobs

1. **`gateway-source-registry-contract-001` patch / új job** — ellenőrizze és
   szinkronizálja a `cic-mcp-session` registry-bejegyzés `query_capabilities[]` listáját
   a "Decisions Proposed" 5. pontban javasolt 6 értékkel (`timeline`/`context_pack`/
   `hybrid`/`fts`/`vector`/`status`/`source_refs`), lásd "Risks" első tétele.
2. **`factory-session-bridge-001`** (Phase 2, a job-spec szerint) — a következő logikai
   lépés, amely a factory job session_id-t a session catalog-hoz kapcsolja; ennek a
   jobnak a session-oldali tool-választása konzisztens kell legyen az itt rögzített
   "Session MCP API Surface" táblával.
3. **`session-context-pack-v1-001`** (Phase 2, a job-spec szerint) — a tényleges
   `compile_context`-implementáció első verziója, amely VALÓDI hívást tesz a 7 tool
   közül legalább egyre, és ez a job kontraktusa adja a "mit kell fordítania" alapot;
   ez a job lenne az első, ami `experimental`-ből `candidate`-be tudná emelni ezt a
   kontraktust (a "Target" szekció "status indoklás" szerint).
4. **(opcionális) `cic-mcp-session` explicit trust-mező hozzáadása tool-szintre** — ha a
   "Risks" második tételében jelzett következtetés-alapú trust-besorolás
   instabilnak bizonyul gyakorlatban, egy `cic-mcp-session`-oldali job explicit
   `trust` kulcsot adhatna minden tool visszatérési dict-jéhez, ami megszüntetné a
   gateway-oldali következtetés szükségességét.
