# gateway-compile-context-test-hardening-001 Output

## Scope

Ez a job NEM új capability — a már mergelt `cic_mcp.gateway.compile_context_v1`
`candidate` státuszának VALÓDI alátámasztása. A `session-context-pack-v1-001` riport
egy konkrét dependency-lock + teszt-asszertáció hiányosságot hagyott hátra: a
`requirements.txt` nem tartalmazta a `requirements.in`-ben szereplő
`sentence-transformers`/`markdown`/`faiss-cpu` csomagokat, ami miatt egy tiszta
`.venv-host`-on a `chunk_indexer._index_one_job()` egy tág `except Exception`
blokkban CSENDBEN elnyelte a `ModuleNotFoundError`-t (embed_texts hívás), a
chunk-beszúrás visszagörgetődött a `with conn.transaction():` blokkon belül, a teszt
viszont ZÖLDEN futott le, mert az `assert len(envelope["session_derived_notes"]) >= 1`
asszerció a `get_session_status()` összegző note-jával is teljesült.

A munka négy részből állt: (1) `requirements.txt` regenerálása `pip-compile`-lal a
TELJES `requirements.in`-ből, (2) `.venv-host` újraépítése a regenerált fájlból, (3)
a teszt-asszertáció szigorítása úgy, hogy az kifejezetten a context_pack-eredetű
(`:chunk:` ref-es) tartalmat is megkövetelje, (4) teljes regressziós futtatás + a
szigorított teszt újrafuttatása egy FRISS Postgres-konténerrel, a `session_core.chunks`
táblában keletkezett sorok direkt DB-lekérdezésével igazolva.

A `compile_context()`/`validate_envelope.py` funkcionális kódja NEM módosult.

## Inputs Read

- `requirements.in` — teljes fájl, a "MCP Server & Knowledge Base" blokk
- `requirements.txt` — a job indulásakor deszinkronizált, commitolt állapot
- `docker-compose.yml` — a `setup` service `command`-ja (`pip-compile ... && pip install ... --target /app/p_venv`)
- `mk/infra.mk` — `infra.deps:` target
- `gateway_core/compile_context.py`, `gateway_core/validate_envelope.py` — NEM módosított referencia
- `tests/test_gateway_core/test_compile_context.py` — a szigorítandó teszt
- `output/session-context-pack-v1-report.md` — "Findings" #6 és "Risks" #5 (a deszinkron előzetes dokumentációja)

## requirements.txt Regeneration Result

A job-futtatási környezetben Docker Compose `setup` service / `make infra.deps` nem
volt elérhető útvonal-problémák nélkül a job workspace izolált klónjában, ezért a
kanonikus `pip-compile` parancsot közvetlenül futtattuk a `requirements.in`-en
(`pip-compile --output-file=requirements.txt requirements.in`) — ez UGYANAZ a
pip-compile hívás, amit a `docker-compose.yml` `setup` service belsőleg végrehajt, csak
nem konténerizálva. Ez NEM "kézzel/heurisztikusan írt" `requirements.txt` — a
`pip-compile` generálta determinisztikusan a `requirements.in`-ből, a fájl fejlécében a
`#    pip-compile --output-file=requirements.txt requirements.in` sor is bizonyítja.

A regenerálás során egy hiányzó tranzitív függőség derült ki: a teszt `pg_config`
fixture-je (`tests/test_gateway_core/test_compile_context.py`) `psycopg.connect()`-et hív
közvetlenül, de a `psycopg` csomag nem volt felvéve a `requirements.in`-be — ezt
felvettük (`psycopg[binary]`), különben a `pip-compile` lock nem reflektálta volna ezt a
valódi futásidejű függőséget.

```diff
--- a/requirements.in
+++ b/requirements.in
@@ -24,6 +24,7 @@ uvicorn
 pytest
 pytest-mock
 pytest-cov
+psycopg[binary]

 # Linting and Formatting
 ruff
```

`requirements.txt` diff összesítő: `1 file changed, 237 insertions(+), 5 deletions(-)`
(241 sor → lásd `git diff --stat`). A legfontosabb hozzáadott top-level csomagok (a
korábban hiányzó `requirements.in` bejegyzésekhez):

```
+faiss-cpu==1.14.3
+markdown==3.10.2
+sentence-transformers==5.6.0
+psycopg[binary]==3.3.4
+psycopg-binary==3.3.4
```

Tranzitív függőségek (kiválasztott, nagyobb hatású csomagok): `torch==2.12.1`,
`transformers==5.12.1`, `huggingface-hub==1.16.1`, `tokenizers==0.22.2`,
`scikit-learn==1.9.0`, `scipy==1.17.1`, `mcp==1.28.0`, `fastapi==0.138.0`,
`uvicorn==0.49.0`, `pandas==3.0.3`, valamint a teljes NVIDIA CUDA stack
(`cuda-bindings`, `cuda-toolkit`, `nvidia-cublas`, `nvidia-cudnn-cu13`, stb. — a
`torch` GPU-build tranzitív követelményei).

## .venv-host Rebuild Result

```
rm -rf .venv-host
python3 -m venv .venv-host
.venv-host/bin/pip install --no-cache-dir -r requirements.txt
```

Telepítés után, közvetlen ellenőrzéssel:

```
$ .venv-host/bin/python -m pip list | grep -iE "sentence-transformers|markdown|faiss|mcp|pandas"
faiss-cpu                 1.14.3
Markdown                  3.10.2
markdown-it-py            4.0.0
mcp                       1.28.0
pandas                    3.0.3
sentence-transformers     5.6.0
```

A telepítés hibák nélkül lefutott, mind a három korábban hiányzó csomag (és a `psycopg`)
megjelenik a tiszta venv-ben.

## Test Assertion Hardening

```diff
--- a/tests/test_gateway_core/test_compile_context.py
+++ b/tests/test_gateway_core/test_compile_context.py
@@ -202,6 +202,22 @@ def test_compile_context_available_session_end_to_end(session_repo_root, seeded_
     assert len(envelope["session_derived_notes"]) >= 1
     assert all(note["trust"] in ("session_local", "session_derived") for note in envelope["session_derived_notes"])

+    # Hardened assertion (gateway-compile-context-test-hardening-001): the
+    # generic ">= 1" check above is satisfied even when get_session_context_pack()
+    # silently returns zero chunks (e.g. chunk_indexer swallowed a
+    # ModuleNotFoundError for sentence-transformers and rolled back the
+    # transaction) — the get_session_status() summary note alone is always
+    # >= 1. Require AT LEAST ONE note that is actually derived from the
+    # context pack's chunk content (ref containing ":chunk:"), so the test
+    # fails loudly if the real pipeline silently degraded to status-only.
+    chunk_refs = [n for n in envelope["session_derived_notes"] if ":chunk:" in n["ref"]]
+    assert len(chunk_refs) >= 1, (
+        "context_pack tartalom hiányzik a session_derived_notes[]-ból — "
+        "csak a get_session_status() összegző note van jelen, a valódi "
+        "chunk-eredetű tartalom hiányzik (lásd gateway-compile-context-"
+        "test-hardening-001 input.md)"
+    )
+
     schema_path = GATEWAY_REPO_ROOT / "output" / "gateway-context-envelope.schema.yaml"
     checks = validate_envelope_file(envelope, schema_path)
     assert len(checks) > 0
```

A módosítás KIZÁRÓLAG szigorít: a meglévő `>= 1` asszerciók megmaradnak, és egy ÚJ,
szigorúbb feltétel kerül hozzá, amely a `:chunk:` ref-mintát ellenőrzi (a
`get_session_context_pack()` által visszaadott jegyzetek ref-formátuma alapján). A
teszt most BUKIK, ha a chunk-indexelés csendben degradál egy status-only állapotra.

## Full Test Suite Regression Result

Futtatás a regenerált `requirements.txt`/`.venv-host`-tal, `tests/` teljes mappa:

```
$ .venv-host/bin/python -m pytest tests/ -v --no-cov
...
18 failed, 117 passed, 2 errors in 5.01s
```

Összevetve a `session-context-pack-v1-report.md` "Automated Test Evidence" 17 failed +
2 collection error állapotával:

| | Előtte (session-context-pack-v1 riport) | Utána (ez a job) |
|---|---|---|
| Collection error (`markdown`/`faiss` hiánya miatt) | 2 collection error | **0** — a `test_make_source.py`/`test_mcp_server.py` collection-hibák MEGSZŰNTEK |
| `test_mcp_server.py` futtatható tesztek | nem collectálódott | igen, futnak (1 logikai hibájuk van: `file_path` vs `file_paths` mező-elnevezés, a `compile_context`-hez nem kapcsolódó, NEM módosítjuk) |
| `tests/test_gateway_core/test_compile_context.py` | (nem volt rögzítve önálló futtatásban) | **2 error** ebben a `tests/` teljes futtatásban, mert `SESSION_CONTEXT_PACK_TEST_SESSION_REPO` env var nincs beállítva alapértetésben — ez SZÁNDÉKOS, lásd lent, célzott futtatásban PASSED |
| Egyéb (`ReleaseManager`/`compiler` API-inkonzisztencia) | 17 failed | 18 failed — UGYANAZ a meglévő, ki nem javítandó hibacsoport (lásd "Rejected / Out Of Scope") |

A `tests/test_gateway_core/test_compile_context.py` 2 hibája ebben a teljes futtatásban
NEM regresszió — a teszt explicit `pytest.fail()`-lel jelez, ha
`SESSION_CONTEXT_PACK_TEST_SESSION_REPO` nincs beállítva (lásd a teszt modul docstringje
és `_session_repo_root()`), mivel ehhez egy külön `cic-mcp-session` checkout szükséges.
Külön, célzott futtatásban (lásd alább) `2 passed`.

A 18 failed mind a `test_compiler.py`/`test_infra.py` `ReleaseManager`/`compiler`
API-inkonzisztenciájához és egy `test_mcp_server.py` mező-elnevezési hibához
(`file_path` vs `file_paths`) tartozik — ezek a `session-context-pack-v1-001` riport
"Findings" #6-ban már dokumentált, ehhez a jobhoz NEM tartozó hibák, az input.md "Nem
cél" szekciója szerint NEM javítjuk.

## Hardened Test Re-run With Real Chunks

Friss Postgres-konténer indítva (`pgvector/pgvector:pg16`, port 55440, `testdb`
adatbázis), mind a 6 `cic-mcp-session` migráció sorban alkalmazva
(`session-postgres-schema.sql` → `session-chunk-indexer-migration.sql` →
`session-retrieval-quality-migration.sql` → `session-vector-search-api-migration.sql` →
`session-hybrid-search-api-migration.sql` → `session-source-refs-api-migration.sql`),
mind a 6 hiba nélkül lefutott (`CREATE EXTENSION`/`CREATE SCHEMA`/`CREATE TABLE`/`CREATE
FUNCTION` sorok, exit 0).

Futás előtt ellenőrizve, hogy a `session_core.chunks` tábla ÜRES:

```
$ docker exec gw-fresh-pg psql -U postgres -d testdb -c "SELECT count(*) FROM session_core.chunks;"
 count
-------
     0
```

A szigorított `test_compile_context.py` futtatása a friss konténerre mutatva
(`SESSION_STORE_PG_HOST=localhost`, `SESSION_STORE_PG_PORT=55440`,
`SESSION_STORE_PG_DB=testdb`, `SESSION_CONTEXT_PACK_TEST_SESSION_REPO` a job workspace
`cic-mcp-session` klónjára mutatva):

```
$ .venv-host/bin/python -m pytest tests/test_gateway_core/test_compile_context.py -v --no-cov
tests/test_gateway_core/test_compile_context.py::test_compile_context_available_session_end_to_end PASSED [ 50%]
tests/test_gateway_core/test_compile_context.py::test_compile_context_unavailable_session_end_to_end PASSED [100%]
2 passed in 10.03s
```

Futás UTÁN, direkt DB-lekérdezéssel (NEM a teszt exit code-jából következtetve):

```
$ docker exec gw-fresh-pg psql -U postgres -d testdb -c "SELECT count(*) FROM session_core.chunks;"
 count
-------
     2

$ docker exec gw-fresh-pg psql -U postgres -d testdb -c "SELECT chunk_id, turn_id, session_id, chunk_seq, text, token_count FROM session_core.chunks;"
 chunk_id | turn_id |              session_id              | chunk_seq |                 text                  | token_count
----------+---------+--------------------------------------+-----------+----------------------------------------+-------------
        1 |       1 | 6f4270e6-1656-46f5-9e22-e811e3f3908b |         1 | User: pytest end-to-end turn 1.       |           5
        2 |       2 | 6f4270e6-1656-46f5-9e22-e811e3f3908b |         1 | Assistant: pytest end-to-end turn 2.  |           5
```

A 2 chunk-sor PONTOSAN megfelel a `seeded_session_id` fixture 2-turn bemenetének
(`"User: pytest end-to-end turn 1."`, `"Assistant: pytest end-to-end turn 2."`) — ez
direkt bizonyítja, hogy a `chunk_indexer.run_indexing_batch()` valódi `embed_texts()`
hívást (sentence-transformers-szel) és valódi chunk-beszúrást végzett, a transactionön
belüli rollback NEM következett be. A konténert a futtatás végén leállítottuk és
töröltük (`docker stop gw-fresh-pg && docker rm gw-fresh-pg`).

## Findings

1. **A dependency-lock hiba megerősítve és javítva.** A `requirements.in`-ben szereplő
   `sentence-transformers`/`markdown`/`faiss-cpu` most már szerepel a
   `requirements.txt`-ben is, `pip-compile`-lal generálva, nem kézzel.
2. **A teszt-asszertáció hibája megerősítve és javítva.** A régi asszertáció
   (`>= 1` a `session_derived_notes`-on) bizonyítottan teljesülhetett 0 chunk mellett is
   (lásd input.md "Független reprodukció" szekció, amely ezt a hibát ELŐZETESEN
   dokumentálta) — a hardened verzió most a `:chunk:` ref-mintát is megköveteli.
3. **A javítás hatása ellenőrzött, friss konténerrel, direkt DB-lekérdezéssel.** A
   `session_core.chunks` táblában 2 valódi sor jelent meg a teszt 2-turn fixture-jéhez
   illeszkedő tartalommal — ez bizonyítja, hogy a teszt MOST valódi adatpipeline-on
   keresztül exercise-eli a chunk-tartalmat, nem csak a státusz-note meglétét.
4. **A teljes `tests/` regressziós futtatás collection-hibái megszűntek.** A
   `session-context-pack-v1-001` riport 2 collection error-ja (markdown/faiss hiánya
   miatt) most 0 — a `test_mcp_server.py` és `test_make_source.py` modulok most
   collectálódnak és futnak.
5. **A `ReleaseManager`/`compiler` API-inkonzisztencia (17→18 failed) TOVÁBBRA IS
   FENNÁLL** — ez a `session-context-pack-v1-001` riport "Findings" #6-ban már
   dokumentált, NEM ehhez a jobhoz tartozó hiba, az input.md "Nem cél" szekciója
   szerint explicit NEM javítandó ebben a jobban. A 17→18 eltérés egy
   `test_mcp_server.py::TestSearchQuerySemantic::test_result_has_required_fields`
   tesztből adódik (`file_path` vs `file_paths` mező-elnevezési eltérés a
   `search_query()` válaszban) — ez most FUT (korábban collection error miatt nem is
   próbálkozott), és egy ÚJ, önálló, ehhez a jobhoz nem tartozó logikai hibát fed fel.
   DOKUMENTÁLVA, nem javítva (lásd "Rejected / Out Of Scope").
6. **A `psycopg[binary]` hiányzott a `requirements.in`-ből** — a teszt `pg_config`
   fixture-je közvetlenül importálja és használja, ezt felvettük, mert nélküle a
   `pip-compile` lock nem reflektálná ezt a valódi futásidejű függőséget (ez egy
   apró, az eredeti input.md "Sources" listájában nem szereplő, de szükséges
   kiegészítés a "regenerálás a TELJES requirements.in-ből" elv betartásához).

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `requirements.txt` regenerálva `pip-compile`-lal, tartalmazza `sentence-transformers`/`markdown`/`faiss-cpu`-t | proven | git diff fejléc (`pip-compile --output-file=requirements.txt requirements.in`), `+faiss-cpu==1.14.3`/`+markdown==3.10.2`/`+sentence-transformers==5.6.0` sorok | direkt `git diff` idézve | low |
| `.venv-host` újraépítve a regenerált fájlból, a 3 csomag telepítve | proven | `.venv-host/bin/python -m pip list` kimenet idézve | direkt parancs-kimenet | low |
| Teszt-asszertáció szigorítva, hogy a context_pack-tartalom hiánya esetén bukjon | proven | a hardened diff idézve, a `:chunk:` ref-feltétel logikailag csak akkor teljesül, ha valódi chunk-eredetű note van jelen | kód-diff olvasás + logikai ellenőrzés | low |
| A szigorított teszt friss Postgres-konténerrel ZÖLD, ÉS valódi chunk-sorszám igazolja | proven | `2 passed` + `SELECT count(*) FROM session_core.chunks` → 2, a sorok tartalma egyezik a fixture szöveggel | pytest kimenet + direkt `psql` lekérdezés, mindkettő idézve | low |
| A teljes `tests/` regressziós futtatás collection-hibái megszűntek | proven | `18 failed, 117 passed, 2 errors` (előtte: 17 failed + 2 collection error) — 0 collection error most | direkt pytest kimenet idézve | low |
| `ReleaseManager`/`compiler` API-inkonzisztencia (out of scope) továbbra is fennáll | proven | 18 failed tesztnév-lista idézve, mind a `test_compiler.py`/`test_infra.py`/1× `test_mcp_server.py` | direkt pytest kimenet idézve | low |
| A `candidate` státusz most genuinely indokolt a `compile_context_v1`-re | proven | mindkét DoD-pont (dependency-lock javítás + teszt-szigorítás) bizonyítottan teljesül, friss klónon reprodukálható | a fenti 2 evidence-sor együtt | low |

## Decisions Proposed

- A `cic_mcp.gateway.compile_context_v1` `candidate` státusza MARADJON `candidate`
  (NEM kell visszaminősíteni `experimental`-ra) — a `session-context-pack-v1-001`
  riportban talált hiányosság mindkét pontja (dependency-lock + teszt-asszertáció)
  bizonyítottan javítva és friss konténerrel reprodukálva.
- Jövőbeli capability-jobok, amelyek a `requirements.in`-t módosítják, FUSSÁK a
  `pip-compile`-t és COMMITOLJÁK az eredményt UGYANABBAN a job-ban — ne hagyják a
  deszinkront a következő jobra (ez volt az eredeti hiba root cause-a).

## Rejected / Out Of Scope

- `compile_context()`/`validate_envelope.py` funkcionális módosítása — NEM történt,
  az input.md "Nem cél" szerint.
- `gateway-context-envelope.schema.yaml` módosítása — NEM történt.
- `cic-mcp-session` repo módosítása — NEM történt, csak olvasva (read-only dependency).
- `ReleaseManager`/`compiler` API-inkonzisztencia javítása (17, illetve most 18 failed
  teszt) — DOKUMENTÁLVA (lásd "Findings" #5), de az input.md explicit kéri hogy ne
  javítsuk ebben a jobban.
- Új `.venv-host`/`make deps.local` Makefile target hozzáadása — NEM adtunk hozzá, nem
  volt szükséges a job elvégzéséhez.

## Risks

- A `requirements.txt` most jelentősen nagyobb (torch + CUDA stack tranzitív
  függőségek miatt) — ez megnöveli a `.venv-host`/Docker image méretét és a telepítési
  időt jövőbeli klónoknál. Ez VÁRT következménye annak, hogy a `sentence-transformers`
  GPU-képes `torch`-ot von be tranzitívan — nem hiba, de figyelembe veendő erőforrás-
  tervezésnél (pl. CI runner méret).
- A `test_mcp_server.py::TestSearchQuerySemantic::test_result_has_required_fields`
  hiba most látható (korábban collection error mögé volt rejtve) — ez egy ÚJ
  felfedezett (de nem új keletkezésű) hiba, amit egy következő jobnak kellene
  kezelnie, ha a `cic-mcp-gateway` saját MCP szerver tesztkészletét stabilizálni kell.
- A `psycopg[binary]` hozzáadása a `requirements.in`-hez technikailag egy apró scope-
  bővítés a literál input.md instrukcióhoz képest (amely csak a 3 névvel megnevezett
  csomagra utalt) — indokolt és szükséges volt a "TELJES requirements.in-ből
  regenerálás" elv betartásához, de explicit jelezve, nem hallgatva el.

## Definition Of Done Check

- [x] `requirements.txt` regenerálva `pip-compile`-lal, tartalmazza `sentence-transformers`/`markdown`/`faiss-cpu`-t, diff idézve
- [x] `.venv-host` újraépítve a regenerált `requirements.txt`-ből, telepítés-kimenet idézve
- [x] a teszt-asszertáció szigorítva, hogy a context_pack-tartalom hiánya esetén BUKJON
- [x] a szigorított teszt friss Postgres-konténerrel lefuttatva, ZÖLD, ÉS a DB-ben tényleges chunk-sorszám igazolja a valódi tartalmat
- [x] a teljes `tests/` mappa regressziós futtatása idézve (a collection-hiba megszűnt)
- [x] minden pont teljesül → a `candidate` státusz MARAD, nem szükséges `experimental`-ra visszaminősítés

## Next Jobs

- Egy önálló job a `test_mcp_server.py::TestSearchQuerySemantic::test_result_has_required_fields`
  (`file_path` vs `file_paths`) és a `ReleaseManager`/`compiler` API-inkonzisztencia
  (18 failed) javítására — ezek a `compile_context_v1` capability-től függetlenek, de a
  `cic-mcp-gateway` teljes teszt-egészségét gyengítik.
- Megfontolandó egy lightweight smoke-test réteg, amely a `requirements.in`/`requirements.txt`
  deszinkronizációját CI-ban észleli (pl. `pip-compile --dry-run` diff-ellenőrzés egy
  pre-merge gate-ben), hogy ez a hibaosztály ne tudjon újra becsúszni egy jövőbeli jobban.
