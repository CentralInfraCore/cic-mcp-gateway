# cic-mcp-gateway-mcp-write-confinement-fix-001 Output

## Scope

Ez a job egy külső biztonsági review-ban feltárt path-traversal / write-confinement
hibát zár a `cic-mcp-gateway` repóban. A `mcp-server/server.py` (byte-azonos a
`cic-mcp-session`/`cic-mcp-knowledge`/`cic-mcp-shared`/`cic-mcp-gateway` mind a négy
repójában, a `base-repo` öröksége) két `@mcp.tool()`-jelölt függvénye —
`update_companion()` és `record_decision()` — egy MCP-klienstől kapott
`file_path`/`companion_path` paramétert ABSZOLÚT útvonalként közvetlenül elfogadta,
MINDEN `SOURCE_DIR`-en-belüliség-ellenőrzés NÉLKÜL, majd `p.open("w")`-vel írt rá.
Ez egy MCP-kliens számára lehetővé tette, hogy bármilyen, a futó processz által
írható fájlt felülírjon a hoszton, nem csak a `source/` könyvtáron belüli companion
YAML-okat.

A job KIZÁRÓLAG a `cic-mcp-gateway` repót javítja — a másik 3 érintett repóban
(`cic-mcp-session`, `cic-mcp-knowledge`, `cic-mcp-shared`) párhuzamos, külön jobok
futnak ugyanezzel a logikával. A jobban két másik, alacsony kockázatú, bundle-ölt
javítás is benne van: a `project.yaml` `metadata.name: base` driftjének javítása, és
a `.mcp.json.tpl`-ben hiányzó `"cic-gateway"` MCP szerver bejegyzés hozzáadása (ezt
az 5. feladatpontot csak ez a job tartalmazza, a testvér-jobok nem).

## Inputs Read

- `mcp-server/server.py` — TELJES fájl (1662 sor): `SOURCE_DIR` definíció
  (1167. sor), `update_companion()` (1486-1556. sor), `record_decision()`
  (1560-1637. sor), `claim_task`/`complete_task`/`fail_task`/`_find_promptmaps()`
  (1261-1482. sor)
- `project.yaml` — TELJES fájl, `metadata.name: base` (2. sor),
  `compiler_settings.component_name: base` (114. sor, NEM ennek a jobnak a
  hatóköre, érintetlen maradt)
- `.mcp.json.tpl` — TELJES fájl (a meglévő `"cic-graph"` bejegyzés)
- `cic-mcp-session/.mcp.json.tpl` (referenciaként, két helyen ellenőrizve:
  `/home/sinkog/sync/claude_factory/CIC/cic-mcp-session/.mcp.json.tpl` és
  `/home/sinkog/sync/git.partners/CentralInfraCore/CIC-MCPs/cic-mcp-session/.mcp.json.tpl`,
  byte-azonos) — a `"cic-session"` bejegyzés mintája
- `mcp-server/gateway_server.py` — TELJES fájl, ellenőrizve hogy `FastMCP("cic-gateway")`-t
  exponál, és hogy a `.mcp.json.tpl`-be felvett `"cic-gateway"` bejegyzés tényleg ezt a
  szkriptet indítja helyesen
- `mk/infra.mk`, `Makefile` — `PYTHON := ./p_venv/bin/python`, `mcp.config` target,
  megerősítve hogy a repo TÉNYLEGES, élő venv-konvenciója `p_venv`, NEM `.venv-host`
  (az utóbbi egy korábbi job, `gateway-context-pack-production-wiring-001`, saját
  ad-hoc teszt-venv-je volt, nem a `.mcp.json.tpl`/Makefile sablon-konvenciója)
- `tests/test_tools/test_mcp_server.py` — TELJES fájl, az `import server as mcp_server`
  + `patch.object(mcp_server, "load_kb", ...)` minta, amit a write-confinement
  tesztek is követnek

## Vulnerability Reproduction (Before Fix)

Grep megerősítés (a két érintett függvényre):

```
$ grep -rn "def update_companion\|def record_decision" --include="*.py" mcp-server/ | grep -v test_
mcp-server/server.py:1486:def update_companion(
mcp-server/server.py:1560:def record_decision(
```

Saját reprodukció — `update_companion()`, a JAVÍTÁS ELŐTTI kóddal, egy `SOURCE_DIR`-en
kívüli, előzetesen létező `/tmp/cic_vuln_poc_outside_source_dir.yaml` fájlra hívva:

```
SOURCE_DIR = .../cic-mcp-gateway/source
target outside SOURCE_DIR? True
target exists before call: True
target contents BEFORE: description: original-untouched-content
update_companion result: {'success': True, 'path': '/tmp/cic_vuln_poc_outside_source_dir.yaml',
  'updated_fields': ['description'],
  'message': 'Updated 1 field(s). Commit to trigger Vault Transit signing.'}
target contents AFTER: description: PWNED by PoC -- write-confinement vulnerability proof
```

A `success: True` válasz és a tényleges fájltartalom-csere bizonyítja: a kód a
`p.open("w")`-ig eljutott, és TÉNYLEGESEN ÍRT egy `SOURCE_DIR`-en kívüli fájlba.

Saját reprodukció — `record_decision()`, a JAVÍTÁS ELŐTTI kóddal (a `load_kb()`
mockolva, mert a függvény azt mindig meghívja még explicit `companion_path` esetén is
— ez egy másodlagos, e jobban kívül eső apróság, nem a fő sebezhetőség):

```
target outside SOURCE_DIR? True
target contents BEFORE: agent_decisions: []
record_decision result: {'success': True, 'path': '/tmp/cic_vuln_poc_record_decision.yaml',
  'message': 'Decision recorded in agent_decisions[0]. Commit to persist.'}
target contents AFTER: agent_decisions:
- node_id: poc-node
  decision: PWNED via record_decision
  timestamp: '2026-06-24T17:37:16.225331+00:00'
```

MINDKÉT függvény ténylegesen, igazolhatóan írt egy `SOURCE_DIR`-en kívüli fájlba a
javítás előtt.

## Confinement Check Implementation

Új helper, `mcp-server/server.py:1170-1198`, a `SOURCE_DIR` definíció (1167. sor)
közvetlen közelében:

```python
def _resolve_within_source_dir(file_path: str) -> Path:
    """..."""
    p = Path(file_path)
    if not p.is_absolute():
        p = SOURCE_DIR / file_path

    resolved = p.resolve()
    resolved_source_dir = SOURCE_DIR.resolve()

    if not resolved.is_relative_to(resolved_source_dir):
        raise ValueError(
            f"path escapes SOURCE_DIR, refused: {resolved} not within {resolved_source_dir}"
        )

    return resolved
```

A path-felépítés a régi logikát követi (abszolút marad abszolút, relatív
`SOURCE_DIR`-hez illesztett), de MINDKÉT oldalt `.resolve()`-olja, és
`Path.is_relative_to()`-val — NEM string-prefix-szel — ellenőrzi a tényleges
containment-et. Symlink- vagy `..`-alapú escape-re is működik, mert a `.resolve()`
feloldja ezeket MIELŐTT az összehasonlítás megtörténik.

Bevezetve mindkét hívó helyen, a path-felépítés UTÁN, de a `p.open()` ELŐTT:

- `update_companion()`, `mcp-server/server.py:1513-1516` — lecseréli a régi
  `p = Path(file_path); if not p.is_absolute(): p = SOURCE_DIR / file_path` blokkot
  egy `try: p = _resolve_within_source_dir(file_path) except ValueError: return
  {"success": False, "message": "path escapes SOURCE_DIR, refused"}` blokkra, ÍRÁS/OLVASÁS
  MEGKÍSÉRLÉSE NÉLKÜL.
- `record_decision()`, `mcp-server/server.py:1645-1648` — a meglévő path-feloldás
  (explicit `companion_path` VAGY node_id-ből származtatott candidate) UTÁN, a
  `p.exists()` ellenőrzés UTÁN, de a `p.open()` ELŐTT kapja meg ugyanezt a
  `try/except ValueError` blokkot. Ez lefedi MINDKÉT útvonalat, ahogyan a végső `p`
  előáll (explicit kliens-megadott `companion_path` ÉS a node_id-ből levezetett
  candidate is át kell mennie a containment-checken, mielőtt írásra kerül).

`claim_task`/`complete_task`/`fail_task` biztonsága megerősítve grep-pel, NEM
módosítva:

```
$ grep -n "_find_promptmaps\|def claim_task\|def complete_task\|def fail_task" mcp-server/server.py
1261:def _find_promptmaps() -> list[Path]:
1329:    for pm_path in _find_promptmaps():
1376:    for pm_path in _find_promptmaps():
1426:def claim_task(task_id: str, repo: str = "") -> dict:
1435:    for pm_path in _find_promptmaps():
1445:def complete_task(task_id: str, repo: str = "", result_note: str = "") -> dict:
1456:    for pm_path in _find_promptmaps():
1466:def fail_task(task_id: str, reason: str, repo: str = "") -> dict:
1476:    for pm_path in _find_promptmaps():
```

Mindhárom kizárólag `_find_promptmaps()` (env-konfigurált `PROMPTMAP_PATHS` VAGY
`SOURCE_DIR.rglob("PROMPTMAP.yaml")`) eredményeit iterálja — sosem vesz át
kliens-megadott abszolút path-ot írás céljából. Ez a scope már biztonságos volt,
nem lett módosítva.

## Real Test Proof — Rejection AND No-Regression

Új teszt-osztályok a `tests/test_tools/test_mcp_server.py`-ban (a fájl meglévő
`import server as mcp_server` + `patch.object(mcp_server, "load_kb", ...)`
mintáját követve): `TestResolveWithinSourceDir`, `TestUpdateCompanionWriteConfinement`,
`TestRecordDecisionWriteConfinement`. Mindegyik `tmp_path` + `monkeypatch.setattr(
mcp_server, "SOURCE_DIR", ...)` izolációt használ.

Tényleges pytest kimenet (csak az új teszteket szűrve):

```
$ p_venv/bin/python -m pytest tests/test_tools/test_mcp_server.py -v -k "WriteConfinement or ResolveWithinSourceDir"
collecting ... collected 20 items / 13 deselected / 7 selected

tests/test_tools/test_mcp_server.py::TestResolveWithinSourceDir::test_path_inside_source_dir_resolves PASSED [ 14%]
tests/test_tools/test_mcp_server.py::TestResolveWithinSourceDir::test_path_escaping_source_dir_raises PASSED [ 28%]
tests/test_tools/test_mcp_server.py::TestResolveWithinSourceDir::test_dotdot_escape_raises PASSED [ 42%]
tests/test_tools/test_mcp_server.py::TestUpdateCompanionWriteConfinement::test_rejects_path_outside_source_dir_no_write PASSED [ 57%]
tests/test_tools/test_mcp_server.py::TestUpdateCompanionWriteConfinement::test_legit_companion_inside_source_dir_still_updates PASSED [ 71%]
tests/test_tools/test_mcp_server.py::TestRecordDecisionWriteConfinement::test_rejects_path_outside_source_dir_no_write PASSED [ 85%]
tests/test_tools/test_mcp_server.py::TestRecordDecisionWriteConfinement::test_legit_companion_inside_source_dir_still_updates PASSED [100%]

======================= 7 passed, 13 deselected in 6.93s =======================
```

`update_companion()` REJECTION eset (`test_rejects_path_outside_source_dir_no_write`):
egy `SOURCE_DIR`-en kívüli `outside.yaml` fájlt előre létrehoz, hívja
`update_companion(file_path=str(outside), description="SHOULD BE REFUSED")`-tel,
asszertál `result["success"] is False`, `"escapes SOURCE_DIR" in result["message"]`,
ÉS hogy a fájl tartalma VÁLTOZATLAN maradt (`outside.read_text() ==
"description: original-untouched-content\n"`).

`update_companion()` NO-REGRESSION eset
(`test_legit_companion_inside_source_dir_still_updates`): `SOURCE_DIR`-en belüli
companion YAML-ra hívva, asszertál `result["success"] is True` ÉS hogy a fájl
tényleg frissült.

Ugyanez a két eset megismételve `record_decision()`-re
(`TestRecordDecisionWriteConfinement` osztály) — mindkettő `load_kb`-t mockolva
(`{"nodes": {}}`), mert a `companion_path` explicit megadásakor a `load_kb()` hívás
egyébként irreleváns lenne a teszt szempontjából.

A teljes test fájl futtatásakor (`pytest tests/test_tools/test_mcp_server.py -v`)
20 teszt közül 19 PASSED, 1 FAILED
(`TestSearchQuerySemantic::test_result_has_required_fields`, `file_path` vs.
`file_paths` kulcsnév-eltérés a `search_query()` visszatérési értékében) — ez a
hiba a JAVÍTÁS ELŐTTI kódon (`git stash`-elve) IS ugyanígy reprodukálódik, tehát
előzetesen létező, e jobtól FÜGGETLEN, e job hatókörén KÍVÜLI hiba, nem
regresszió.

## project.yaml Fix

```yaml
# előtte
metadata:
  name: base

# utána
metadata:
  name: cic-mcp-gateway
```

Csak a `metadata.name` mező változott. `description`/`tags`/`version`/`license`/
`owner`/`validatedBy` érintetlen maradt. A `compiler_settings.component_name: base`
(114. sor) egy KÜLÖN mező, NEM lett módosítva — ez nem ennek a jobnak a hatóköre.

## .mcp.json.tpl Fix

A javítás előtti tartalom:

```json
{
  "mcpServers": {
    "cic-graph": {
      "command": "{{REPO_ROOT}}/p_venv/bin/python",
      "args": [
        "{{REPO_ROOT}}/mcp-server/server.py"
      ],
      "env": {
        "KB_DATA_DIR": "{{REPO_ROOT}}/kb_data/pkl"
      }
    }
  }
}
```

Hozzáadott `"cic-gateway"` bejegyzés (a `cic-mcp-session/.mcp.json.tpl`-ben már
bevált `"cic-session"` minta — host-natív interpreter, saját szerver-script,
`PYTHONPATH` env forwarding — szerkezetét követve):

```json
"cic-gateway": {
  "command": "{{REPO_ROOT}}/p_venv/bin/python",
  "args": [
    "{{REPO_ROOT}}/mcp-server/gateway_server.py"
  ],
  "env": {
    "PYTHONPATH": "{{REPO_ROOT}}"
  }
}
```

Megjegyzés: a `cic-mcp-session/.mcp.json.tpl` `"cic-session"` bejegyzése
`.venv-host/bin/python`-t használ — ez `cic-mcp-session` repo saját, élő
venv-konvenciója. A `cic-mcp-gateway` repóban a MEGLÉVŐ `"cic-graph"` bejegyzés
(amit ez a job NEM módosított) ÉS a `mk/infra.mk` (`PYTHON := ./p_venv/bin/python`)
ÉS a `Makefile` `mcp.config` target egyaránt `p_venv`-et használ mint a repo
TÉNYLEGES, élő interpreter-konvencióját — ezért az új `"cic-gateway"` bejegyzés is
`p_venv/bin/python`-t használ, NEM `.venv-host`-ot. Ez NEM új konvenció kitalálása,
hanem a meglévő `"cic-graph"` bejegyzés interpreter-választásának követése + a
`"cic-session"` minta STRUKTÚRÁjának (saját script, `PYTHONPATH` env) átvétele. A
meglévő `"cic-graph"` bejegyzés bit-pontosan érintetlen maradt.

Megerősítve: `gateway_server.py` (`mcp-server/gateway_server.py`) a `p_venv`-ből
importálva ténylegesen `FastMCP("cic-gateway")`-t exponál:

```
$ p_venv/bin/python -c "
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, 'mcp-server')
os.environ['PYTHONPATH'] = '.'
import gateway_server
print('gateway_server imported OK, mcp name:', gateway_server.mcp.name)
"
gateway_server imported OK, mcp name: cic-gateway
```

A `.mcp.json.tpl` JSON-validitása ellenőrizve `python3 -m json.tool`-lal — érvényes.

## Findings

- A sebezhetőség MINDKÉT érintett függvényben (`update_companion`,
  `record_decision`) valós volt és tényleges fájlírásig vezetett, nem csak
  elméleti — a reprodukció bizonyítja.
- `record_decision()` mindig meghívja `load_kb()`-t, akkor is, ha `companion_path`
  explicit megadott (a node_id-alapú lookup ága ekkor irreleváns lenne) — ez egy
  másodlagos, ezen jobon KÍVÜLI hatékonysági/kód-tisztasági apróság, NEM
  biztonsági hiba, NEM lett javítva (nem volt a Feladat része).
- `record_decision()` node_id-ből levezetett companion-path ága
  (`Path(src).with_suffix(".yaml")`, ha `src` KB-ben abszolút útvonalként van
  tárolva) ELMÉLETBEN szintén escape-elhetne — ez a job a végső `p`-re alkalmazza a
  containment-checket MINDKÉT ág (explicit `companion_path` ÉS node_id-derivált
  candidate) UTÁN, így ez az eset is lefedett, anélkül hogy a node_id-lookup
  logikáját módosítani kellett volna.
- A `tests/test_tools/test_mcp_server.py`-ban egy előzetesen létező, e jobtól
  független teszthiba van (`test_result_has_required_fields`) — megerősítve hogy a
  javítás előtti kódon IS reprodukálódik, tehát nem regresszió.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `update_companion()` a javítás előtt SOURCE_DIR-en kívüli fájlba írt | proven | "Vulnerability Reproduction" szekció, tényleges before/after fájltartalom | saját Python-hívás, `success: True` + fájltartalom-csere | — |
| `record_decision()` a javítás előtt SOURCE_DIR-en kívüli fájlba írt | proven | "Vulnerability Reproduction" szekció, tényleges before/after fájltartalom | saját Python-hívás (load_kb mockolva), `success: True` + fájltartalom-csere | — |
| `_resolve_within_source_dir()` `Path.resolve()` + `Path.is_relative_to()` alapú, NEM string-prefix | proven | `mcp-server/server.py:1170-1198` kódidézet | kódolvasás + `TestResolveWithinSourceDir` 3 teszt (inside/absolute-escape/dotdot-escape) | — |
| `update_companion()` path-traversal-t elutasít, fájl nem módosul | proven | pytest kimenet, `test_rejects_path_outside_source_dir_no_write` PASSED | tényleges pytest futás, fájltartalom-asszerció | — |
| `update_companion()` legitim eset továbbra is működik (no regression) | proven | pytest kimenet, `test_legit_companion_inside_source_dir_still_updates` PASSED | tényleges pytest futás | — |
| `record_decision()` path-traversal-t elutasít, fájl nem módosul | proven | pytest kimenet, `test_rejects_path_outside_source_dir_no_write` (Record osztály) PASSED | tényleges pytest futás, fájltartalom-asszerció | — |
| `record_decision()` legitim eset továbbra is működik (no regression) | proven | pytest kimenet, `test_legit_companion_inside_source_dir_still_updates` (Record osztály) PASSED | tényleges pytest futás | — |
| `claim_task`/`complete_task`/`fail_task` biztonságos, nem módosítva | proven | grep kimenet, `_find_promptmaps()`-csak hivatkozás | grep + kódolvasás, diff nem érinti ezeket a függvényeket | — |
| `project.yaml` `metadata.name` javítva, más mező érintetlen | proven | `git diff project.yaml`, 1 sor változás | git diff | — |
| `.mcp.json.tpl` új `"cic-gateway"` bejegyzés, `"cic-graph"` érintetlen, `"cic-session"` minta követve | proven | `git diff .mcp.json.tpl`, JSON validáció, `gateway_server.py` import-teszt | git diff + `python3 -m json.tool` + Python import-teszt | — |
| Az 1 meglévő test failure (`test_result_has_required_fields`) nem regresszió | proven | `git stash` + ugyanaz a teszt ugyanúgy FAILED a javítás előtti kódon | tényleges pytest futás stash-elt állapoton | alacsony — out-of-scope, nem ez a job hatóköre |

## Decisions Proposed

- A `_resolve_within_source_dir()` helper minden jövőbeli, client-supplied
  útvonalat elfogadó `@mcp.tool()` függvényhez kötelezően használandó minta
  legyen ebben a repóban (és a testvér-repókban is, ha a párhuzamos jobok átveszik).
- A `record_decision()` `load_kb()`-mindig-hívás apróságát egy KÜLÖN, kisebb
  hatékonysági jobban érdemes javítani (nem biztonsági kritikus, nem ennek a
  jobnak a hatóköre).

## Rejected / Out Of Scope

- `claim_task`/`complete_task`/`fail_task` módosítása — már biztonságos, csak
  grep-pel megerősítve, kódot nem módosítottunk.
- `project.yaml` `description`/`tags`/`version`/`license`/`owner`/`validatedBy`
  mezőinek módosítása — kizárólag `metadata.name` változott.
- A másik 3 repó (`cic-mcp-session`/`cic-mcp-knowledge`/`cic-mcp-shared`)
  javítása — külön, párhuzamos jobok feladata.
- A generikus KB-szerver egyéb funkcióinak (search/focus_pack/stb.) módosítása.
- `record_decision()` `load_kb()`-mindig-hívás apróságának javítása — lásd
  "Decisions Proposed".

## Risks

- Alacsony: a fix kizárólag két függvényt érint, additív jellegű (egy új
  early-return ág, ha a path escape-el), a legitim use case-eket a teszt
  bizonyítottan nem töri.
- Alacsony: a `.mcp.json.tpl` változás additív (új mcpServers kulcs), a meglévő
  `"cic-graph"` bejegyzést bizonyítottan nem érinti.
- Alacsony: a `project.yaml` `metadata.name` változás dokumentációs jellegű,
  runtime viselkedést nem érint.
- Megjegyzés: a `record_decision()` node_id-derivált companion-path ágának
  KB-forrású (`node.get("source_file")` / `node.get("file_path")`) bemenete jelen
  állapotban a meglévő, nem ezen jobban módosított `load_kb()`/KB-adatból
  származik — ha ez a KB-adat valaha kliens által közvetlenül befolyásolhatóvá
  válna, a containment-check (amely jelenleg a VÉGSŐ `p`-re alkalmazott, mindkét
  ágra) változatlanul védelmet ad, mivel az ellenőrzés a path-felépítés UTÁN, az
  `open()` ELŐTT fut MINDKÉT ágra.

## Definition Of Done Check

- [x] a sebezhetőség REPRODUKÁLVA a javítás ELŐTT, TÉNYLEGES kimenettel (lásd
  "Vulnerability Reproduction")
- [x] `_resolve_within_source_dir()` implementálva, `mcp-server/server.py:1170-1198`
- [x] MINDKÉT érintett függvény javítva (`update_companion`:
  `mcp-server/server.py:1513-1516`, `record_decision`:
  `mcp-server/server.py:1645-1648`)
- [x] valós teszt: path-traversal ELUTASÍTVA ÉS legitim eset TOVÁBBRA IS működik,
  MINDKÉT függvényre, TÉNYLEGES pytest kimenettel (lásd "Real Test Proof")
- [x] `claim_task`/`complete_task`/`fail_task` biztonsága megerősítve grep-pel
  (NEM módosítva)
- [x] `project.yaml` `metadata.name` javítva, más mező érintetlen
- [x] `.mcp.json.tpl`-ben ÚJ `"cic-gateway"` bejegyzés, `"cic-graph"` bejegyzés
  érintetlen, `"cic-session"` minta követve
- [x] claim-evidence tábla kitöltve, nem üres

## Next Jobs

- `cic-mcp-session-mcp-write-confinement-fix-001`,
  `cic-mcp-knowledge-mcp-write-confinement-fix-001`,
  `cic-mcp-shared-mcp-write-confinement-fix-001` — a testvér-jobok ugyanezt a
  logikát viszik át a másik 3 repóba (párhuzamosan futnak, ez a job nem nyúl
  beléjük).
- Opcionális, KÜLÖN job: `record_decision()` `load_kb()`-mindig-hívás
  hatékonysági javítása (csak ha `companion_path` explicit megadott, ne hívja a
  KB-betöltést).
