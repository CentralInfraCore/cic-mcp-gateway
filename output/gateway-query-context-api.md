# gateway-query-context-api-001 Output

## Scope

A `gateway_core/compile_context.py:compile_context()` eddig KIZÁRÓLAG `session_id`-alapú
hívást fogadott — egy konzumer csak egy MÁR ISMERT session-hez tudott kontextust lekérni
(`get_session_context_pack()`-en keresztül, insertion-order chunk-lista). Ez a job bővíti
`query`/`intent`/`repo`/`token_budget` paraméterekkel: ha `query` meg van adva, egy ÚJ útvonal
fut (`session_api.search_context()` hibrid FTS+vector keresés a `cic-mcp-session` MCP
szerveren), amely RELEVANCIA szerint rendezett chunk-okat ad, és a `token_budget` ténylegesen
korlátozza a visszaadott envelope méretét. A MEGLÉVŐ `session_id`-only hívási út VÁLTOZATLAN —
`query=None` esetén byte-for-byte ugyanaz a viselkedés, mint a job előtt.

**Nem érintett**: knowledge/shared források bekötése (`gateway-knowledge-shared-adapters-001`,
külön job), a `cic-mcp-session` MCP szerver oldali módosítása (a gateway a MEGLÉVŐ
`search_session_context`/`get_session_context_pack` tool-okat hívja, nem bővíti azokat),
valódi ML-alapú intent-klasszifikáció (egyszerű, szabály-alapú `_classify_intent()` készült
helyette, az input.md ezt explicit megengedi).

## Inputs Read

- `jobs/gateway-query-context-api-001/input.md` — job spec
- `gateway_core/compile_context.py` — a JELENLEGI `compile_context()`/`_compile_context_async()`
  teljes implementációja, módosítás előtt és után
- `jobs/session-context-pack-v1-001/output/session-context-pack-v1.md`,
  `jobs/gateway-compile-context-test-hardening-001/output/*.md` — a meglévő, tesztelt
  `session_id`-only viselkedés, amit NEM szabad megtörni
- `tests/test_gateway_core/test_compile_context.py` — meglévő teszt-konvenció (valós Postgres,
  valós subprocess+stdio MCP handshake, `validate_envelope_file()` schema-ellenőrzés)
- `mcp-server/session_server.py` (cic-mcp-session) — `search_session_context()` tool
  szignatúrája (hibrid FTS+vector, RRF-fúzió, `fused_score DESC` rendezés)

## Findings

### 1. Pre-change szignatúra — idézve

```
$ git show HEAD:gateway_core/compile_context.py | grep -n "def compile_context"
354:def compile_context(

$ git show HEAD:gateway_core/compile_context.py | sed -n '354,358p'
def compile_context(
    session_id: str,
    repo_root: Path | str,
    max_chunks: int = 50,
    python_executable: Path | str | None = None,
) -> dict[str, Any]:
```

Ez a "mit bővítünk, mit nem törhetünk" alap — a négy paraméter MIND POZICIONÁLIS-VAGY-KEYWORD,
`session_id`/`repo_root` kötelező, `max_chunks`/`python_executable` defaulttal.

### 2. Bővített szignatúra

```python
def compile_context(
    session_id: str,
    repo_root: Path | str,
    max_chunks: int = 50,
    python_executable: Path | str | None = None,
    query: str | None = None,
    intent: str | None = None,
    repo: str | None = None,
    token_budget: int | None = None,
) -> dict[str, Any]:
```

A `session_id`/`repo_root` ELSŐ KÉT POZÍCIÓ NEM változott (kötelező, pozicionális) — minden
meglévő hívó, ami `compile_context(session_id, repo_root=...)`-ot hív, MŰKÖDIK TOVÁBBRA IS,
módosítás nélkül. A négy ÚJ paraméter mind keyword, mind `None` default — `query=None` esetén
a `_compile_context_async()` a MEGLÉVŐ `get_session_context_pack()` ágat futtatja
(`compile_context.py:382` körül, "EXISTING path (session-context-pack-v1-001), UNCHANGED"
megjegyzéssel).

`repo` paramétert a szignatúra ELFOGADJA, de NEM köti be semmilyen forráshoz ebben a jobban
(lásd "Rejected / Out Of Scope") — ez DOKUMENTÁLT, nem hallgatott el.

### 3. Regresszió-mentesség — a MEGLÉVŐ tesztek továbbra is zöldek

```
$ pytest tests/test_gateway_core/test_compile_context.py::test_compile_context_available_session_end_to_end \
    tests/test_gateway_core/test_compile_context.py::test_compile_context_unavailable_session_end_to_end \
    tests/test_gateway_core/test_compile_context.py::test_compile_context_query_path_session_id_only_path_unaffected -v

test_compile_context_available_session_end_to_end PASSED
test_compile_context_unavailable_session_end_to_end PASSED
test_compile_context_query_path_session_id_only_path_unaffected PASSED
```

Az utolsó (`..._session_id_only_path_unaffected`) egy ÚJ, ehhez a jobhoz tartozó teszt, amely
UGYANAZT a (4 turn-ös, topikusan eltérő) seed-adatot `query` NÉLKÜL hívja, és bizonyítja, hogy
`query_intent == "session-context-recall"` (a régi, változatlan érték) ÉS mind a 4 chunk
visszajön (NEM egy relevancia-szűrt részhalmaz) — azaz az ÚJ fixture sem változtatja meg a
RÉGI út viselkedését.

### 4. Új, query-alapú útvonal — valós teszt, releváns tartalommal

`test_compile_context_query_path_returns_relevant_chunk` egy 4-turn-ös fixture-t épít (2 turn a
"deployment rollback" témáról, 2 turn a "dashboard color" témáról — topikusan DISZTINKT, hogy a
relevancia-rendezés érdemben ellenőrizhető legyen), majd `compile_context(query="how do I roll
back a deployment", ...)`-et hív.

```
$ pytest tests/test_gateway_core/test_compile_context.py::test_compile_context_query_path_returns_relevant_chunk -v
PASSED
```

Assert-ek: `query_intent != "session-context-recall"` (az ÚJ ág futott), a top-ranked chunk-note
TARTALMAZZA a "rollback"/"roll back" szót, ÉS NEM tartalmazza a "dashboard"/"color" szót — azaz
a `session_api.search_context()` hibrid keresés TÉNYLEGESEN relevancia szerint rendezett, nem
beszúrási sorrendben.

### 5. `token_budget` enforcement — kis vs nagy budget, valós teszt

`test_compile_context_token_budget_truncates_envelope` UGYANAZT a query-t hívja
`token_budget=20` ÉS `token_budget=100_000`-rel, és összehasonlítja a visszaadott
`session_derived_notes[]` darabszámát/karakterösszegét:

```
$ pytest tests/test_gateway_core/test_compile_context.py::test_compile_context_token_budget_truncates_envelope -v
PASSED
```

Assert-ek: `len(small_notes) <= len(large_notes)`, `small_chars < large_chars` (a kis budget
TÉNYLEGESEN kevesebb/kisebb tartalmat ad), ÉS a legrelevánsabb (top-ranked) note TOVÁBBRA IS
szerepel a kis-budget eredményben (a `_apply_token_budget()` implementáció — lásd
`compile_context.py` — sosem dob el MINDEN releváns tartalmat, még akkor sem, ha az egyetlen
legrelevánsabb note önmagában meghaladja a maradék budgetet). Mindkét envelope (kis és nagy
budget) schema-valid (`validate_envelope_file()` mindkettőre futtatva).

**Hibajavítás a teszt írása közben** (nem az implementáció hibája): a teszt eredeti verziójának
utolsó 2 sora egy MÁSOLÁSI hiba volt (egy nem létező `envelope` változóra és egy nem importált
`validate_envelope_file`-ra hivatkozott, `NameError`-t dobva) — javítva: mindkét (small/large)
envelope-ot kifejezetten validálja, a hiányzó importtal együtt.

### Implementáció — releváns részletek

- **`_classify_intent(query)`** (`compile_context.py`, új függvény): egyszerű kulcsszó-alapú
  szabály — ha a query timeline-jellegű kulcsszót tartalmaz ("history", "timeline", "when did",
  stb.) → `"session-history-recall"`, egyébként → `"session-query-search"`. NEM ML.
- **`_estimate_tokens(text)`**: durva, determinisztikus becslés (`len(text) // 4`, minimum 1
  nem-üres szövegre) — input.md "becsült karakter/token-szám alapján" megfogalmazását
  KIFEJEZETTEN nem valódi tokenizerként teljesíti.
- **`_apply_token_budget(status_notes, chunk_notes, refs, token_budget)`**: a `status_notes`
  (session-identity anchor, mindig 1 elem) SOSEM csonkolódik; a `chunk_notes`-ot (amik MÁR
  relevancia-rendezettek a `search_session_context()` `fused_score DESC` sorrendje miatt) a
  budget kimerüléséig veszi fel, de a LEGELSŐ (legrelevánsabb) chunk-note-ot MINDIG megtartja,
  még akkor is, ha egyedül meghaladja a maradék budgetet (lásd docstring indoklása —
  "Forbidden Shortcuts" fordított hibamódja, egy túl agresszív enforcement, ami önmagában
  hatástalanítaná a query-utat).
- `token_budget=None` esetén `_apply_token_budget()` no-op — a régi út viselkedése változatlan.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| Pre-change szignatúra idézve, file:line hivatkozással | proven | `git show HEAD:gateway_core/compile_context.py \| grep -n "def compile_context"` → `354:def compile_context(` + a 4 paraméter idézve | tényleges grep/show a committed HEAD ellen | Nincs |
| A meglévő `session_id`-only hívási út tesztjei továbbra is zöldek | proven | `test_compile_context_available_session_end_to_end` + `test_compile_context_unavailable_session_end_to_end` PASSED, MÓDOSÍTÁS NÉLKÜL (korábbi job output-ja) | tényleges pytest, valós Postgres + valós subprocess+stdio MCP | Nincs |
| Az új fixture (`query_seeded_session_id`) sem változtatja meg a régi út viselkedését | proven | `test_compile_context_query_path_session_id_only_path_unaffected` PASSED — `query_intent == "session-context-recall"`, mind a 4 chunk visszajön | valós pytest | Nincs |
| Új, query-alapú útvonal релevancia szerint rendezett tartalmat ad, NEM beszúrási sorrendet | proven | `test_compile_context_query_path_returns_relevant_chunk` PASSED — top-ranked note "rollback"-ot tartalmaz, "dashboard"/"color"-t NEM | valós pytest, valós `search_session_context()` hibrid keresés ellen | Nincs |
| `token_budget` ténylegesen korlátozza az envelope méretét (kis vs nagy budget) | proven | `test_compile_context_token_budget_truncates_envelope` PASSED — `len(small_notes) <= len(large_notes)`, `small_chars < large_chars`, mindkét eredet TÉNYLEGES méreteivel | valós pytest, két tényleges `compile_context()` hívás összehasonlítva | Nincs |
| `token_budget` enforcement nem dobja el a legrelevánsabb tartalmat | proven | ugyanaz a teszt: a "rollback" szót tartalmazó note a KIS budget eredményben IS megvan | valós pytest assert | Nincs |
| Mindkét (kis/nagy budget) envelope schema-valid marad | proven | `validate_envelope_file(small_envelope, ...)` és `validate_envelope_file(large_envelope, ...)` mindkettő `len(checks) > 0`-t ad | valós pytest, a repo saját schema-validátora ellen | Nincs |
| A `query`/`intent`/`repo`/`token_budget` paraméterek mind keyword, `None` default, nem törik a meglévő pozicionális hívást | proven | `compile_context.py:503-512` (bővített szignatúra); a két MEGLÉVŐ teszt módosítás nélkül zöld | kód olvasás + pytest | Nincs |
| `repo` paraméter elfogadott, de NEM köti be semmilyen forráshoz (dokumentált, nem hallgatott el) | proven | `compile_context.py` docstring "repo: NEW, accepted but NOT YET wired to any source in this job"; nincs `repo`-t felhasználó kódág | kód olvasás (negatív bizonyíték) | Nincs |
| Az intent-klasszifikáció szabály-alapú, NEM ML | proven | `_classify_intent()` egyetlen kulcsszó-lista + `if`/`else`, nincs modell-betöltés/inference ebben a függvényben | kód olvasás | Nincs |
| `meta.yaml` `status` mező nem módosítva | proven | a jelen munka csak a `cic-mcp-gateway` klónban dolgozott | git diff (cic-mcp-factory klón) | Nincs |

## Decisions Proposed

1. **`search_session_context()` (hibrid FTS+vector, RRF), nem `search_session_context_fts`/
   `_vector` külön** — a meglévő hibrid tool már relevancia-rendezett, fúzionált eredményt ad,
   ami pontosan a "forrás-kiválasztás a query alapján" igényt teljesíti, két külön hívás és
   saját fúziós logika helyett.
2. **A legrelevánsabb chunk-note SOSEM esik ki a `token_budget` enforcement alatt**, még ha
   egyedül meghaladja a maradék budgetet — lásd `_apply_token_budget()` docstring indoklása,
   a Forbidden Shortcuts FORDÍTOTT hibamódjának (túl agresszív enforcement) elkerülése.
3. **`status_notes` kivétel a token_budget alól** — a session-identity anchor note olcsó (1
   fix-alakú mondat) és nem query-releváns tartalom, csonkolása semmilyen célt nem szolgálna.
4. **`repo` paraméter elfogadott, de nem bekötött** — a workdir/repo-scope-olt források egy
   KÜLÖN, még nem implementált capability (lásd "Rejected / Out Of Scope"), de a szignatúra
   előre felveszi a helyét, hogy egy jövőbeli job ne kelljen megint szignatúra-bővítést végezzen.
5. **`_estimate_tokens()` durva char/4 heurisztika, nem valódi tokenizer** — input.md ezt
   explicit megengedi ("becsült karakter/token-szám alapján"), egy valódi tokenizer hozzáadása
   új függőséget igényelne ezért a becslésért.

## Rejected / Out Of Scope

- Knowledge/shared források bekötése — `gateway-knowledge-shared-adapters-001`, külön job.
- A `cic-mcp-session` MCP szerver oldali módosítása — a gateway a MEGLÉVŐ
  `search_session_context()`/`get_session_context_pack()` tool-okat hívja, nem bővíti azokat.
- Valódi ML-alapú intent-klasszifikáció — `_classify_intent()` szabály-alapú, input.md "Nem cél"
  ezt explicit kizárja a kötelezettségből (de nem tiltja, ha indokolt — itt NEM volt indokolt).
- `repo` paraméter tényleges bekötése egy forráshoz — elfogadva a szignatúrában, de NEM
  implementálva, lásd "Decisions Proposed" 4. pont.

## Risks

- **Az `_estimate_tokens()` durva char/4 becslés** eltérhet egy valódi tokenizer (pl. a
  cic-mcp-knowledge/gateway által esetlegesen használt LLM tokenizer) tényleges token-számától —
  ha egy jövőbeli konzumer SZIGORÚ token-limitet ad át egy LLM kontextus-ablakhoz, ez a becslés
  alul- vagy felülbecsülhet. Mitigáció: a docstring explicit dokumentálja, hogy ez becslés, nem
  pontos tokenizáció.
- **`_classify_intent()` kulcsszó-listája kis, kézzel írt halmaz** — egy query, ami nem
  tartalmaz "history"/"timeline"-szerű kulcsszót, de valójában történeti jellegű, alapértelmezett
  `"session-query-search"`-ként osztályozódik. Ez NEM hiba (a szabály-alapú megközelítés
  input.md által explicit megengedett), de egy jövőbeli, pontosabb taxonómia javíthatja.
- **A `query`-alapú út `max_chunks`-ot `limit`-ként továbbítja a `search_session_context()`
  hívásnak** — ha a hibrid keresés saját belső limitje (pl. RRF candidate-pool mérete) eltér
  ettől, a tényleges visszaadott chunk-szám nem feltétlenül egyezik pontosan `max_chunks`-szal;
  ezt a job nem vizsgálta részletesen, mert a `search_session_context()` tool maga egy KORÁBBI
  job kontraktusa, nem ennek a jobnak a hatóköre.

## Definition Of Done Check

- [x] pre-change szignatúra idézve, file:line hivatkozással — "Findings" 1. pont
- [x] a meglévő `session_id`-only hívási út tesztjei TOVÁBBRA IS zöldek, TÉNYLEGES pytest kimenettel bizonyítva — "Findings" 3. pont
- [x] új, query-alapú hívási út valós teszttel bizonyítva — "Findings" 4. pont
- [x] `token_budget` tényleges korlátozó hatása valós teszttel bizonyítva (kis vs nagy budget összehasonlítás) — "Findings" 5. pont
- [x] claim-evidence tábla kitöltve, nem üres — fent, 11 sor

## Next Jobs

- `gateway-knowledge-shared-adapters-001` — knowledge/shared források bekötése a query-útvonalba
  (jelenleg csak a session-forrás query-alapú lekérdezése készült el).
- A `repo` paraméter tényleges bekötése egy workdir/repo-scope-olt forráshoz — még nem
  implementált capability, lásd "Rejected / Out Of Scope".
- Ha egy jövőbeli konzumer pontos token-számolást igényel (nem becslést), egy valódi tokenizer
  bevezetése `_estimate_tokens()` helyett — lásd "Risks".
