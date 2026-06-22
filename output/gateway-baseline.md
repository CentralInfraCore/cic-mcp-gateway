# gateway-repo-baseline-or-bootstrap-001 Output

## Scope

Ez a job **audit + kontraktus-vázlat**, NEM implementáció. A `cic-mcp-gateway` repo
bootstrap-ja (`base-repo` `mcp/main` specializációból, `CLAUDE.md` +
`docs/{hu,en}/architecture.{md,yaml}` gateway-specifikus customizálása) már megtörtént
out-of-band (`bootstrap_status: done_out_of_band_2026-06-20`). Ez a report:

1. grep-bizonyítékkal megállapítja a repo jelenlegi tényleges (kód-szintű) státuszát,
2. szintetizálja a minimális gateway felelősségi kört,
3. felvázolja a source registry kezdeti határát,
4. felvázolja a `GatewayContextEnvelope` kezdeti határát,
5. javasolja a következő gateway contract jobot.

Nem cél: routing logika, MCP tool-ok, tényleges gateway-kód, teljes schema, vagy a
`cic-mcp-session`/`cic-mcp-shared`/`cic-mcp-knowledge` repók módosítása.

## Inputs Read

- `cic-mcp-factory/.cic-context/factory-docs/architecture.md` — "cic-mcp-gateway" Igen/Nem
  szekció (NORMATÍV)
- `cic-mcp-factory/.cic-context/factory-docs/execution-phases.md` — "Phase 1B - cic-mcp-gateway
  Baseline" szekció (NORMATÍV)
- `cic-mcp-factory/.cic-context/corpus/normalized/thead-review-2026-06-20.yaml` —
  `dec-thead-0005` ("cic-mcp-gateway is a trust-domain aware context compiler, not a generic
  search proxy") és `architecture_summary.gateway_layer`
- `cic-mcp-gateway/CLAUDE.md` (a már customizált gateway-scope dokumentáció, teljes terjedelem)
- `cic-mcp-gateway/docs/hu/architecture.md` és `cic-mcp-gateway/docs/en/architecture.md`
  (teljes terjedelem, mindkét nyelvi variáns)
- `cic-mcp-gateway/source/` tartalma (könyvtárlistázással)
- `cic-mcp-gateway/mcp-server/server.py`, `cic-mcp-gateway/make_source.py` (fejrész + grep)
- `cic-mcp-gateway/features/feature-001/spec.md`, `feature-002/spec.md`
- `cic-mcp-gateway/tests/` (fájllista)
- `cic-mcp-gateway` git remote + git log (lineage ellenőrzés)
- `mcp__cic-graph__kb_status` (Boot sequence 1. lépés)

## Repo Status Audit

**Megállapított státusz: `scaffold`.**

A repo könyvtárszerkezete, build tooling-ja és MCP-szerver infrastruktúrája létezik (ez a
`base-repo` `mcp/main` öröksége), a `CLAUDE.md` és `docs/{hu,en}/architecture.md` már
gateway-specifikus szöveget tartalmaz — de **nincs egyetlen gateway-specifikus Python
implementáció** (routing, source registry, `GatewayContextEnvelope` kód). A dokumentáció maga
explicit kimondja: "nincs még gateway-specifikus implementáció" (`CLAUDE.md` "Jelenlegi
állapot" szekció), "A fenti adatfolyamból jelenleg semmi nincs implementálva" (`docs/hu/architecture.md`
"Jelenlegi állapot" szekció). Ez nem `bootstrap-required` (a bootstrap már megtörtént — a
dokumentáció-réteg készen van), és nem `exists` (nincs futó/élő implementáció) — pontosan a
`scaffold` kategóriát fedi: van kód, de szándékosan nincs gateway-specifikus runtime híd.

### Grep bizonyíték

Parancs (a job-spec szerinti, korrigált útvonal-szűréssel — a relatív `find`/`grep` kimenet
`./tools/...` formában jön, a sima `/tools/` mintára a `grep -v` nem fogott rá, ezért
`tools/` mintával futtattam újra):

```
$ grep -rn "gateway" --include="*.py" . | grep -v test_ | grep -v "tools/" | grep -v "p_venv/"
(0 találat, exit=1)
```

Direkt ellenőrzés a két kulcsfájlon:

```
$ grep -n "gateway" mcp-server/server.py make_source.py
(0 találat, exit=1)
```

**0 gateway-specifikus találat** a `mcp-server/server.py`-ban és a `make_source.py`-ban — ezek
fejrésze (`server.py` docstring: "Graph MCP server for CIC knowledge base stored in PKL files
(legacy format supported)... Read-only MCP server that exposes: token search... chunk/node
lookup... graph traversal...") egyértelműen a generikus `base-repo` KB-template kódja, NEM
gateway-specifikus implementáció.

Az eredeti, módosítatlan grep-parancs (`grep -v "/tools/"`, leading `./` nélküli minta) 4
hamis-pozitív találatot adott `tools/go.meta.gen.py` és `tools/py.meta.gen.py`-ban (pl.
`tools/go.meta.gen.py:296: tags.update(['core', 'gateway'])`) — ezek a release-tooling
metadata-generátor TAG-listájában szereplő `"gateway"` string (egy meta-tag enum tagja, nem
gateway-domain logika), és a `tools/` explicit ki van zárva a spec szerint. Ez egyben
bizonyítja a "tiltott rövidítés" elvét: a `"gateway"` string puszta előfordulása egy fájlban
nem jelenti gateway-implementációt.

További megerősítő bizonyíték:

```
$ ls source/
.gitkeep   (0 byte, kizárólag git-placeholder — a könyvtár tényleg üres)

$ find features -type f
features/feature-001/spec.md   (generikus "feature spec management" placeholder, base-repo öröksége)
features/feature-002/spec.md   (generikus "git management system" placeholder, base-repo öröksége)

$ find tests -type f -name "*.py" | xargs grep -ln "gateway"
(0 találat)

$ git remote -v
origin  git@github.com:CentralInfraCore/cic-mcp-gateway.git (fetch/push)
(nincs külön "base-repo" remote bekötve a klónban — a CLAUDE.md erre hivatkozik mint
jövőbeli lehetőségre, jelenleg nincs élő kapcsolat)

$ git log --oneline -5
1cff065 Merge pull request #2 ... docs/architecture-customization
7d121fe docs: customize docs/{hu,en}/architecture.{md,yaml} for gateway component scope
2d33f09 Merge pull request #1 ... docs/component-customization
03f28d1 docs: customize README/CLAUDE.md for cic-mcp-gateway component scope
0f78405 feat: add knowledge.sources.yaml -> .gitmodules generator (thead03 design)
```

A git history is azt mutatja: az eddigi commit-ok kizárólag dokumentáció-customizációt és a
generikus `base-repo` öröklött tooling-ot tartalmazzák, nincs gateway-domain feature commit.

## Findings

1. A `mcp-server/server.py` és `make_source.py` szó szerint a `base-repo` MCP-template KB-
   generátor/szerver kódja — TF-IDF/cosine similarity gráf építés, FastMCP stdio szerver,
   12 generikus tool (`search_query`, `search_token`, `neighbors`, `focus_pack`, stb.). Ezek
   hasznosak lesznek a gateway saját belső KB-jéhez (pl. a saját `CLAUDE.md`/docs
   indexeléséhez), de NEM a gateway *domain*-funkcióját (query intent, source routing,
   envelope-összeállítás) implementálják.
2. A `source/` könyvtár valóban üres (csak `.gitkeep`) — ez konzisztens a dokumentációval,
   nincs még betöltött forrásanyag a gateway saját KB-jéhez.
3. A `CLAUDE.md` és `docs/{hu,en}/architecture.md` már tartalmazza a normatív Igen/Nem
   határokat és a trust modellt — ez a dokumentáció-réteg készen van, ez indokolja a
   `bootstrap_status: done_out_of_band` állítást.
4. Nincs gateway-specifikus teszt (`tests/` alatt 0 `gateway` találat) — ez konzisztens azzal,
   hogy nincs gateway-specifikus kód, amit tesztelni kellene.
5. A `docs/hu/architecture.md` és `docs/en/architecture.md` explicit kimondja a tervezett
   `GatewayContextEnvelope` mezőlistát (`answer_type`, `query_intent`, `scope`, `sources_used`,
   `trust_summary`, `canonical_facts`, `workdir_facts`, `session_derived_notes`,
   `shared_memory_notes`, `conflicts`, `proof_requirements`, `refs`) és a következő job-sorrendet
   (`gateway-context-envelope-contract-001` → `gateway-session-adapter-contract-001`) — ez egy
   erős, már meglévő bemenet a 4. és 5. szekcióhoz, NEM ennek a jobnak kell kitalálnia
   nulláról.
6. A `kb_status` MCP hívás sikeres volt, a cic-graph KB friss (6 cache hit, 1 miss, 1 elem),
   minden pkl/faiss/bm25 artifact létezik a `kb_data/pkl/` alatt — a Boot sequence 1. pontja
   teljesítve, a tényállítások KB-alapú megerősítésre alkalmasak voltak.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| A `cic-mcp-gateway` repo jelenlegi státusza `scaffold` (nem `exists`, nem `bootstrap-required`) | proven | `grep -rn "gateway" --include="*.py" . \| grep -v test_ \| grep -v "tools/" \| grep -v "p_venv/"` → 0 találat; `grep -n "gateway" mcp-server/server.py make_source.py` → 0 találat | grep futtatás, fájlfejrész-olvasás | low |
| `mcp-server/server.py`/`make_source.py` a generikus base-repo KB-template kódja, nem gateway-specifikus | proven | docstring/fejrész idézve ("Graph MCP server for CIC knowledge base stored in PKL files... Read-only MCP server that exposes: token search...") + 0 gateway-string találat | fájl-fejrész olvasás + grep | low |
| `source/` üres | proven | `ls -la source/` → csak `.gitkeep`, 0 byte | könyvtárlistázás | low |
| A gateway dokumentáció-réteg (`CLAUDE.md`, `docs/{hu,en}/architecture.md`) gateway-specifikus, nem template | proven | teljes fájltartalom idézve/szintetizálva fent, git log 4 customizációs commit | fájl olvasás + git log | low |
| A gateway NEM generikus proxy (`route_query != search_all`) | proven | `CLAUDE.md` "Tiltott rövidítések" szekció + `architecture.md` "Forbidden shortcuts" szekció szó szerint tartalmazza ezt a tételt | dokumentum idézet | low |
| A gateway NEM tárol session raw adatot | proven | `CLAUDE.md` trust modell: `owns_raw_storage: false`; `architecture.md` "Nem" lista: "raw event store" | dokumentum idézet (YAML blokk) | low |
| Nincs gateway-specifikus teszt | proven | `find tests -type f -name "*.py" \| xargs grep -ln "gateway"` → 0 találat | grep futtatás | low |
| A `GatewayContextEnvelope` mezőlista-javaslat (lent) konzisztens a már létező doc-tervvel | proven | `docs/{hu,en}/architecture.md` "Tervezett adatfolyam" szekció mezőlistája szó szerint idézve | fájl olvasás | low |
| A következő job javaslat (`gateway-context-envelope-contract-001`) helyes sorrend | proven | `execution-phases.md` Phase 1B "Elso capability-k" listája + `docs/architecture.md` capability-job sorrend explicit egyezik | dokumentum-keresztreferencia | low |

## Minimal Gateway Responsibility

A gateway egyetlen feladata: **bejövő agent-query-t trust-domain forrásokra route-olni, és az
eredményt egységes, trust-jelölt kontextus-csomaggá (`GatewayContextEnvelope`) összeállítani**.
Konkrétan:

- felismeri a query intent-et (mit keres az agent, milyen scope-ban),
- a source registry alapján eldönti, MELYIK trust-domain forrást (session/shared/knowledge)
  kell megkérdezni — nem mindenkit egyszerre, nem keresőmotor-szerű "search_all",
- a forrásokból kapott válaszok közti konfliktust/proof-igényt felszínre hozza, nem elsimítja,
- az `GatewayContextEnvelope`-ot összeállítja és visszaadja az agent-facing API-n,
- soha nem hoz létre saját igazságot (`does not create truth`) — a trust-szintet a forrásból
  öröklve jelöli, nem upgrade-eli.

Explicit NEM-felelősségek (mind a `cic-mcp-factory/architecture.md`, mind a gateway saját
`CLAUDE.md`-je szerint, egyezően):

- **raw event store** — ez a `cic-mcp-session` réteg felelőssége, a gateway nem tárol
  session-eseményeket
- **embedding store** — nincs saját vektor-index, nem helyettesíti a forrásréteg keresését
- **factory runner** — nem futtat capability-jobokat, nem a `cic-mcp-factory` szerepét veszi át
- **canonical promotion** — nem dönt arról, mi válik canonical tudássá; ez a
  `cic-mcp-knowledge` review/promotion folyamatának felelőssége

A trust modell (`gateway_role: trust_domain_context_compiler`, `owns_raw_storage: false`,
`owns_embedding_store: false`, `returns_trust_envelope: true`) ezt a négy NEM-et kódolja
deklaratív formába — minden jövőbeli gateway-kódnak ennek kell megfelelnie.

## Source Registry — Initial Boundary

(Vázlat — NEM implementáció, NEM teljes schema. Bemenet a `gateway-source-registry-contract-001`
jobhoz.)

Egy "source" a gateway szempontjából egy trust-domain réteg, amit a gateway lekérdezhet — NEM
maga a réteg implementációja, csak egy regisztrált belépési pont rá. Kezdeti source-lista:

```yaml
sources:
  - source_id: cic-mcp-session
    trust_domain: session_local        # session_local / session_derived
  - source_id: cic-mcp-shared
    trust_domain: shared_mixed         # mixed / candidate / reviewed_shared
  - source_id: cic-mcp-knowledge
    trust_domain: canonical            # reviewed/canonical
  - source_id: cic-mcp-workdir
    trust_domain: workdir_local        # aktuális repo/worktree/branch/diff állapot
```

Egy source registry bejegyzés minimális metaadat-mezői (mezőlista szinten, nem teljes schema):

| Mező | Típus | Jelentés |
|---|---|---|
| `source_id` | string | egyedi azonosító (pl. `cic-mcp-session`) |
| `trust_domain` | enum | a forrás trust-szintje (`session_local`, `shared_mixed`, `canonical`, `workdir_local`) |
| `owns_raw_storage` | bool | a forrás maga tárol-e raw adatot (a gateway-nek ez mindig `false` kell legyen, a *forrásnak* lehet `true`) |
| `returns_trust_envelope` | bool | a forrás már trust-jelölt válaszformátumot ad-e vissza, vagy a gateway-nek kell becsomagolnia |
| `query_capabilities` | list[string] | milyen query-típusokat tud kiszolgálni (pl. `full_text`, `vector`, `timeline`, `graph`) |
| `canonical` | bool | a forrás tartalma canonical-e (alapból csak `cic-mcp-knowledge` review után) |

Ez egy kiinduló határ — a tényleges schema, validáció, és a registry betöltési mechanizmusa a
`gateway-source-registry-contract-001` jobé.

## GatewayContextEnvelope — Initial Boundary

(Vázlat — NEM teljes schema, NEM implementáció. Bemenet a
`gateway-context-envelope-contract-001` jobhoz.)

A `docs/{hu,en}/architecture.md` "Tervezett adatfolyam" szekciója már felsorol egy
mezőlista-javaslatot (`answer_type`, `query_intent`, `scope`, `sources_used`, `trust_summary`,
`canonical_facts`, `workdir_facts`, `session_derived_notes`, `shared_memory_notes`,
`conflicts`, `proof_requirements`, `refs`). Ez a job ezt NEM írja át, csak megerősíti és a
spec által kért minimális hármas-bontásra vetíti:

| Kategória | Releváns mezők a doc-tervből | Jelentés |
|---|---|---|
| **honnan jött a kontextus** | `sources_used`, `query_intent`, `scope` | melyik source_id-kből épült a válasz, milyen kérdésre |
| **mi a tartalom** | `canonical_facts`, `workdir_facts`, `session_derived_notes`, `shared_memory_notes`, `refs` | a forrásrétegekből összegyűjtött tényleges tartalom, forrásréteg szerint particionálva |
| **milyen trust-jelölés van rajta** | `trust_summary`, `conflicts`, `proof_requirements` | a tartalom trust-szintje, ismert konfliktusok a forrásrétegek között, mit kell még bizonyítani |

Ez a hármas-bontás a minimális határ, amit ez a job megállapít — a tényleges mezőtípusok,
validáció, és JSON/YAML schema a `gateway-context-envelope-contract-001` jobé.

## Decisions Proposed

1. A repo státusza `scaffold` — ezt rögzítse a következő job spec-je is (ne `bootstrap-required`-
   ként hivatkozzon rá, a bootstrap réteg kész).
2. A `mcp-server/server.py`/`make_source.py` generikus KB-tooling-ot a gateway saját belső
   dokumentáció-indexeléséhez érdemes később felhasználni (pl. a saját `docs/`/`CLAUDE.md`
   tartalmának kereshetővé tételéhez), de ez NEM helyettesíti a gateway domain-logikáját — ezt
   külön döntésként rögzíteni kell, hogy a következő jobok ne keverjék össze a kettőt.
3. A `GatewayContextEnvelope` és a source registry kontraktusát a doc-tervben már lefektetett
   mezőlistára építve kell formalizálni (ne kezdje nulláról a következő job).

## Rejected / Out Of Scope

- routing logika, MCP tool-ok, vagy bármilyen tényleges gateway-kód implementálása — ez NEM
  ennek a jobnak a feladata (lásd Nem cél)
- `cic-mcp-session`/`cic-mcp-shared`/`cic-mcp-knowledge` repók módosítása — nem történt, nem is
  volt indokolt
- `CLAUDE.md`/`docs/architecture.md` átírása — már megtörtént out-of-band, ez a job nem
  duplikálja, csak auditál és szintetizál
- teljes `GatewayContextEnvelope` vagy source registry SCHEMA leszállítása — ez explicit a
  `gateway-context-envelope-contract-001` és `gateway-source-registry-contract-001` jobok
  feladata, ez a job csak a kezdeti határt vázolja
- a `tools/go.meta.gen.py`/`tools/py.meta.gen.py` "gateway" tag-találatainak gateway-
  implementációként való elszámolása — ezek release-tooling meta-tag enumok, nem domain-logika,
  explicit kizárva a Repo Status Audit szekcióban

## Risks

- **Doc/kód divergencia kockázat**: a `docs/{hu,en}/architecture.md` már rögzít egy konkrét
  `GatewayContextEnvelope` mezőlistát és job-sorrendet — ha a következő contract-job ettől
  eltérő mezőneveket választ indoklás nélkül, az inkonzisztenciát okoz a már publikált
  dokumentáció és a tényleges kontraktus között. Mitigáció: a következő job explicit
  hivatkozzon ennek az auditnak a "GatewayContextEnvelope — Initial Boundary" szekciójára.
- **Generic-tooling félreértés kockázat**: a `mcp-server/server.py`/`make_source.py` jelenléte
  könnyen vezethet ahhoz, hogy valaki a repo könyvtárstruktúráját implementált gateway-
  funkcióként hivatkozza. Mitigáció: ez a report explicit grep-bizonyítékkal zárja ki ezt az
  állítást (lásd Forbidden Shortcuts harmadik tétele).
- **Source registry kör-definíció kockázat**: a `cic-mcp-workdir` mint "source" jelenleg a
  `cic-factory` szerepét tölti be (lásd `docs/en/architecture.md`: "current repo/worktree/
  branch/diff (role filled by cic-factory)") — a következő jobnak tisztáznia kell, hogy ez
  külön source-domain-e, vagy a `cic-factory`-n keresztül érhető el csak.

## Definition Of Done Check

- [x] repo státusz (`exists`/`scaffold`/`bootstrap-required`) megállapítva, grep-bizonyítékkal
      → `scaffold`, lásd "Repo Status Audit"
- [x] explicit kijelentve, hogy a gateway NEM generikus proxy (`route_query != search_all`)
      → lásd "Minimal Gateway Responsibility" + Claim-Evidence Matrix sor 5
- [x] explicit kijelentve, hogy a gateway NEM tárol session raw adatot
      → lásd "Minimal Gateway Responsibility" + Claim-Evidence Matrix sor 6
- [x] minimális gateway felelősségi kör szintetizálva (nem csak idézve)
      → lásd "Minimal Gateway Responsibility" (saját szavakkal írt szintézis)
- [x] source registry kezdeti határ felvázolva
      → lásd "Source Registry — Initial Boundary"
- [x] `GatewayContextEnvelope` kezdeti határ felvázolva
      → lásd "GatewayContextEnvelope — Initial Boundary"
- [x] következő gateway contract job javasolva, indoklással
      → lásd "Next Jobs"
- [x] claim-evidence tábla kitöltve, nem üres
      → lásd "Claim-Evidence Matrix" (9 sor)

## Next Jobs

**Javasolt következő job: `gateway-context-envelope-contract-001`**

Indoklás (a saját audit eredményéből, nem csak átmásolva):

1. Ez a job megerősítette, hogy a repo `scaffold` státuszban van — van bootstrap-olt
   infrastruktúra, de nulla domain-logika. A `source registry` és a `GatewayContextEnvelope`
   közül az envelope a logikailag előbbi: a source registry értelmetlen anélkül, hogy
   ismernénk, MILYEN formátumba kell a forrásokból gyűjtött adatot összeállítani — az envelope
   schema definiálja, mit kell egy source-adapternek visszaadnia.
2. A `docs/{hu,en}/architecture.md` már tartalmaz egy konkrét mezőlista-javaslatot ("Tervezett
   adatfolyam" szekció) ÉS egy explicit job-sorrendet (`gateway-context-envelope-contract-001`
   → `gateway-session-adapter-contract-001`), amit ez az audit megerősített és a "GatewayContextEnvelope
   — Initial Boundary" szekcióban hármas-bontásra (honnan/mi/trust) vetített — ez közvetlen,
   azonnal felhasználható bemenet a következő jobhoz, csökkenti az újratervezés kockázatát.
3. Az `execution-phases.md` Phase 1B listája is ezt a sorrendet írja elő
   (`gateway-repo-baseline-or-bootstrap-001` → `gateway-context-envelope-contract-001` →
   `gateway-source-registry-contract-001`) — ez az audit nem talált ellentmondó bizonyítékot,
   ami ettől eltérő sorrendet indokolna.

Másodlagos jelölt (ha az envelope job blokkolva lenne): `gateway-source-registry-contract-001`
— de ennek van egy nyitott kérdése (lásd "Risks" harmadik tétel: `cic-mcp-workdir` mint
source-domain vs. `cic-factory`-n keresztüli elérés), amit tisztázni kell, mielőtt a registry
schema-t formalizálnánk.
