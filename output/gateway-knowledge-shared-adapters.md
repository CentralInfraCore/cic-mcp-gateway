# gateway-knowledge-shared-adapters-001 — Knowledge + Shared source adapterek

**Target repo:** `cic-mcp-gateway`
**Change type:** enhancement
**Status after merge:** candidate
**Branch:** `feature/gateway-knowledge-shared-adapters-001`

---

## 1. Miért kellett (melyik job/repo akadt el nélküle)

A `compile_context()` eddig **egyetlen** forrást konzultált: `cic-mcp-session`
(job: `session-context-pack-v1-001`, majd a query-path `gateway-query-context-api-001`).
A `GatewayContextEnvelope` séma viszont négy tartalom-kategóriát ír elő, ebből
kettő — `canonical_facts[]` (knowledge) és `shared_memory_notes[]` (shared) —
**mindig üres tömbként** került be (`compile_context.py` HEAD:555 / HEAD:558:
`"canonical_facts": []`, `"shared_memory_notes": []`). A gateway tehát nem tudta
felszínre hozni sem a `cic-mcp-knowledge` reviewed/promoted canonical tudást, sem a
`cic-mcp-shared` cross-session memóriát — pont a két forrást, amelyek a
`session_local`-nál magasabb (knowledge) illetve más trust-vokabulárt (shared)
hordoznak. Enélkül a gateway "trust-domain context compiler" szerepe (CLAUDE.md
"Fő határok") csak az egyharmadáig volt kitöltve.

### Pre-change bizonyíték (a job ELŐTT nem volt bekötve)

```
$ git show HEAD:gateway_core/knowledge_adapter.py   → ABSENT (új a jobban)
$ git show HEAD:gateway_core/shared_adapter.py       → ABSENT (új a jobban)
$ git show HEAD:gateway_core/compile_context.py | grep -nE '"canonical_facts": \[\]|"shared_memory_notes": \[\]'
555:        "canonical_facts": [],
558:        "shared_memory_notes": [],
```

A HEAD-en a `knowledge`/`shared` szavak a `compile_context.py`-ben **kizárólag
docstring-kommentként** szerepeltek ("only the cic-mcp-session source is
consulted (cic-mcp-knowledge, cic-mcp-shared, … are NOT wired here)") — semmilyen
futó lekérdezés nem hivatkozott rájuk.

---

## 2. Milyen tool/MCP contract jön létre

| Adapter | Forrás elérése | Hívott felület |
|---|---|---|
| `knowledge_adapter.search_knowledge()` | **valós MCP subprocess** (`mcp.client.stdio`), a `cic-mcp-knowledge` szerver indítása `p_venv/bin/python mcp-server/server.py`, `KB_DATA_DIR` env-fel | `search_query(query, top_k)` → ranked hits (nincs body), majd `get_chunk(chunk_id)` per hit a tartalomért |
| `shared_adapter.search_shared_candidates()` | **közvetlen, READ-ONLY Postgres** (`psycopg`), `SESSION_STORE_PG_*` env (ua. konvenció mint a shared aggregator) | `SELECT … FROM shared_core.candidates WHERE trust = ANY('{candidate,reviewed_shared}') AND keyword_description ILIKE …` |

A launch-konvenciók **nem újra-feltaláltak**: a knowledge a `.mcp.json.tpl`
"cic-graph" entry-jét tükrözi, a shared a `SharedStoreConfig.from_env()`
env-var neveit. Mindkét forrásrepó **kizárólag olvasásra** van használva — nem
módosul, nem pusholódik (lásd 6. pont).

### Wiring a `compile_context`-ben

A query-path (`query is not None`) opcionálisan, **csak ha a hívó bekapcsolta**:
- `knowledge_repo_root` megadva → `KnowledgeServerLaunchConfig` épül → knowledge konzultálva
- `shared_db_config` megadva → shared konzultálva

Default `None` → **a session-only path bájtra változatlan** (backward compat by
construction). A 152 meglévő teszt collection-je törésmentes (lásd 4. pont).

---

## 3. Output schema (per-element trust megőrzés — a job magja)

A séma (`output/gateway-context-envelope.schema.yaml`) szerint:

| Kategória | item required | trust mező | Forrás |
|---|---|---|---|
| `canonical_facts[]` | `[content, ref]` | **NINCS** — a kategóriába kerülés MAGA a canonical jelölés | knowledge ONLY |
| `shared_memory_notes[]` | `[content, trust, ref]` | `enum: mixed \| candidate \| reviewed_shared` — a sor saját trust-ja **verbatim** | shared ONLY |

Megvalósított invariánsok:
- knowledge találat → `canonical_facts` item **pontosan** `{content, ref}` (trust mező sosem szivárog be);
- shared sor → `shared_memory_notes` item `{content, trust, ref}`, a `trust` a DB-sor értéke **változatlanul**;
- a gateway **sosem emel trust-ot**: `candidate` marad `candidate`, `reviewed_shared` marad `reviewed_shared`;
- `mixed` trust **teljesen kizárva** (SQL `WHERE` + a visszatérő soron újra-ellenőrzés, defense-in-depth);
- shared sor **sosem** kerül `canonical_facts`-ba, még `reviewed_shared` esetén sem.

`overall_confidence` levezetése (séma: "MUST be derivable from per_category"):
canonical tartalom jelen → `high`; egyébként session/shared tartalom → `medium`;
elérhetetlen session + nincs canonical/shared → `unverified` (session-only path
változatlan). `shared_memory_notes` per_category: `reviewed_shared` jelen →
`medium`, csak `candidate` → `low`, üres → `not_used`.

---

## 4. Milyen teszt bizonyítja (valós, futtatott)

Fájl: `tests/test_gateway_core/test_knowledge_shared_adapters.py` — **NINCS mock,
nincs in-process import a forrás-szerverek tool-függvényeiből.**

| Teszt | Mit bizonyít | Valós forrás |
|---|---|---|
| `test_knowledge_adapter_real_subprocess` | `search_query`+`get_chunk` valós találatot ad; az item-ben **nincs** `trust` kulcs; a projekció pontosan `{content, ref}` | valós `cic-mcp-knowledge` MCP subprocess, fixture KB BM25/inverted fallback path-en (nincs faiss/embedding artifact) |
| `test_shared_adapter_excludes_mixed_and_preserves_trust` | a `mixed` sor **nem** jelenik meg; `candidate`→`candidate`, `reviewed_shared`→`reviewed_shared` (verbatim); minden trust az `ALLOWED_SHARED_TRUST`-ban | valós Postgres `shared_core.candidates`, 3 beszúrt sor (egy/trust) |
| `test_multi_source_envelope_preserves_per_element_trust` | ≥1 knowledge + ≥1 shared elem egy envelope-ban; canonical item `{content,ref}` only; shared item `{content,trust,ref}`; `overall_confidence=high`; mindkét forrás `sources_used`-ban; egyetlen canonical sem hordoz trust mezőt | **mindkét valós forrás** együtt (`_gather_multi_source` + `_build_envelope`) |

### Futtatási evidence

```
$ docker run -d postgres:16-alpine  (disposable, port-mapped)
$ SESSION_STORE_PG_* + GATEWAY_TEST_KNOWLEDGE_REPO/PYTHON env
$ pytest tests/test_gateway_core/test_knowledge_shared_adapters.py -v
  test_knowledge_adapter_real_subprocess              PASSED
  test_shared_adapter_excludes_mixed_and_preserves_trust  PASSED
  test_multi_source_envelope_preserves_per_element_trust  PASSED
  ================= 3 passed in 10.92s =================

$ pytest --collect-only -q   → 152 tests collected (no import/syntax regression)
```

A knowledge subprocess a meglévő, faiss+mcp+sentence_transformers-telepített
`p_venv`-et használja (`GATEWAY_TEST_KNOWLEDGE_PYTHON`), mert a
`server.py` modul-szinten, guard nélkül importálja a `faiss`/`sentence_transformers`-t
(26/32. sor) — még a fallback path-hez is importálható kell legyen. A KB viszont
**könnyű fixture** (4 pickle: chunks/nodes/edges/inverted), a server BM25/inverted
fallback ágát hajtja, FAISS index és embedding model nélkül.

---

## 5. Milyen státuszban indul

`candidate` (`meta.yaml: capability.status_after_merge: candidate`). Indok: a két
adapter valós forrásokon, valós teszttel bizonyított, de (a) a knowledge subprocess
egy nehéz (faiss+torch) venv-et igényel a target repo `p_venv`-jében, ami éles
deploykörnyezetben még nem standardizált; (b) a teljes 3-forrásos (session ∪
knowledge ∪ shared) **end-to-end, session-first** futás külön, populált session-t
igényel — lásd 7. limitáció. `canonical`-ra promotálás ezek lezárása után.

---

## 6. Registry / target-repo diff

**Új fájlok (`cic-mcp-gateway`):**
- `gateway_core/knowledge_adapter.py` — `KnowledgeServerLaunchConfig` + `search_knowledge()`
- `gateway_core/shared_adapter.py` — `SharedDbConfig` + `search_shared_candidates()` (READ-ONLY)
- `tests/test_gateway_core/test_knowledge_shared_adapters.py`
- `output/gateway-knowledge-shared-adapters.md` (ez a dokumentum)

**Módosított fájl:**
- `gateway_core/compile_context.py` — `_build_envelope` kiegészítve `canonical_facts`/`shared_memory_notes` paraméterekkel (default `[]`); új `_gather_multi_source` + `_shared_per_category` helperek; `_compile_context_async` és a publikus `compile_context` opcionális `knowledge_*` / `shared_db_config` paraméterekkel — mind backward-kompatibilis default `None`-nal.

**Git-fegyelem (input.md szerint betartva):**
- push **kizárólag** `cic-mcp-gateway` `feature/gateway-knowledge-shared-adapters-001`-re;
- `cic-mcp-knowledge` és `cic-mcp-shared` klónok **read-only** — nem módosítva, nem pusholva;
- factory klón: csak lokális commit, **nem** pusholva;
- a `meta.yaml status` mezőt az agent-munka **nem** írja át (a `pending → agent_done` az orchestrátor bookkeeping-je).

---

## 7. Ismert limitációk

1. **Teljes 3-forrásos session-first E2E nincs ebben a tesztben.** A
   `compile_context()` mindig először a session-t kérdezi; a knowledge/shared
   csak a session feloldása után, a query-ágon fut. Ehhez populált session +
   épített session `.venv-host` kell, ami nincs ennek a jobnak a workspace-ében
   (`workplace.repos = knowledge, shared` — session nincs). A multi-source
   bizonyíték ezért a `_gather_multi_source` + `_build_envelope` szintjén, **valós
   knowledge subprocess + valós shared Postgres** felett készült. A session-first
   wrapper-t a meglévő `test_compile_context.py` fedi (külön session-infra).
2. **`superseded_by` szűrés nincs.** Az adapter a spec szerint **csak** trust-ra
   szűr (`candidate`/`reviewed_shared`). Egy `superseded_by IS NOT NULL` sor még
   megjelenhet — a felülírt jelöltek kiszűrése külön capability.
3. **Keyword match = `ILIKE`** a `keyword_description`-on, nem szemantikus/vector
   keresés (a shared-nek nincs MCP query-szervere ebben a scope-ban). Relevance
   ranking = `weight_score DESC`.
4. **Knowledge venv súlyos.** A `server.py` guard nélküli `import faiss` /
   `sentence_transformers` miatt a subprocess venv-be kell a teljes ML-stack még a
   BM25 fallback-hez is. A KB fixture ettől függetlenül könnyű.

---

## 8. Rollback / deprecate út

- **Rollback:** a `feature/gateway-knowledge-shared-adapters-001` PR revert-elésével
  a `compile_context` visszaáll a session-only viselkedésre — mivel minden új
  paraméter default `None`, a session-only call site-ok már a merge előtt is
  pontosan a régi envelope-ot kapják (üres `canonical_facts`/`shared_memory_notes`),
  így a revert nem érint egyetlen meglévő hívót sem.
- **Deprecate (forrásonként):** egy adapter kikapcsolható a hívó oldalon a
  megfelelő config átadásának elhagyásával (`knowledge_repo_root=None` és/vagy
  `shared_db_config=None`) — kódváltozás nélkül. A két modul egymástól független,
  külön deprecálható.
- **Trust-szabály visszavonása tilos:** a `mixed` kizárás és a per-element trust
  megőrzés a séma-kontraktus része; ezek lazítása nem rollback, hanem új
  (review-zandó) capability lenne.
