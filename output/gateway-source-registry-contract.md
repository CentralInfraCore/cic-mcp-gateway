# gateway-source-registry-contract-001 Output

## Scope

Ez a job a `cic-mcp-gateway` **source registry**-jének ELSŐ formális YAML
schema-kontraktusát definiálja. Ez **schema-kontraktus job, NEM implementáció**:
nincs futtatható registry betöltő/validátor kód, nincs routing logika, nincs
adapter implementáció. A leszállított artifact két fájl:
`output/gateway-source-registry.schema.yaml` (a schema maga) és ez a report.

A job a `gateway-context-envelope-contract-001` job által már lerögzített
`sources_used[].source_id`/`trust_domain` enumokra épül — ez a job formalizálja
azt a hiányzó kontraktust, amire a `gateway-context-envelope.schema.yaml`
description-je explicit hivatkozik ("the full source registry contract (field
types, capabilities) is defined by gateway-source-registry-contract-001, not
here"). A job egyben lezárja a `gateway-baseline.md` "Risks" szekciójának
nyitott kérdését: `cic-mcp-workdir` külön source-domain-e, vagy csak a
`cic-factory`-n keresztül érhető el.

Nem cél (lásd input.md "Nem cél"): registry betöltő/validátor FUTTATHATÓ
kódjának megírása, `GatewayContextEnvelope` schema módosítása, tényleges
routing logika vagy adapter kód, `cic-mcp-session`/`cic-mcp-shared`/
`cic-mcp-knowledge`/`cic-mcp-factory` repók módosítása.

## Inputs Read

- `cic-mcp-gateway/output/gateway-baseline.md` — teljes terjedelem, kiemelten
  "Source Registry — Initial Boundary" és "Risks" szekció (a
  `cic-mcp-workdir`/`cic-factory` nyitott kérdés forrása)
- `cic-mcp-gateway/output/gateway-context-envelope.schema.yaml` — teljes
  terjedelem, kiemelten `sources_used[].source_id`/`trust_domain` enum
  deklarációk (192., 202., 446. sor)
- `cic-mcp-gateway/output/gateway-context-envelope-contract.md` — teljes
  terjedelem, kiemelten "Next Jobs" szekció (mit vár el ettől a jobtól) és
  "Risks" negyedik tétele ("Source registry körkörösség kockázat")
- `cic-mcp-gateway/docs/hu/architecture.md` és `cic-mcp-gateway/docs/en/architecture.md`
  — teljes terjedelem, kiemelten a komponens-térkép szöveges diagram
  (`cic-mcp-workdir current repo/worktree/branch/diff (role filled by
  cic-factory)`) és a "Fő határok"/"Boundaries" szekció
- `cic-mcp-factory/.cic-context/factory-docs/architecture.md` — "cic-mcp-gateway"
  szekció + a komponens-térkép szöveges diagramja (`cic-mcp-workdir` saját
  sorként, `cic-mcp-factory` külön sorként szerepel)
- `cic-mcp-factory/.cic-context/factory-docs/execution-phases.md` — "Phase 1B"
  szekció (a job-sorrend megerősítése)
- `mcp__cic-graph__kb_status` (Boot sequence 1. lépés) — eredmény:
  `cache_info` 6 hit / 1 miss / 1 currsize, mind a 6 pkl/faiss/bm25 artifact
  (`chunks.pkl`, `graph_nodes.pkl`, `graph_edges.pkl`, `inverted_index.pkl`,
  `faiss.index`, `bm25.pkl`) `exists: true` — a KB friss és elérhető, a Boot
  sequence teljesítve

## Enum Sync Check

A job-spec KÖTELEZŐ grep-parancsát futtattam a `gateway-context-envelope.schema.yaml`
ellen (a `cic-mcp-gateway` klón gyökeréből):

```
$ grep -n "cic-mcp-session\|cic-mcp-shared\|cic-mcp-knowledge\|cic-mcp-workdir\|session_local\|session_derived\|shared_mixed\|canonical\|workdir_local" \
  output/gateway-context-envelope.schema.yaml | grep -v test_
```

A releváns enum-deklaráció sorok (a teljes kimenetből kiemelve — a teljes
kimenet 40+ sor leíró szöveget is tartalmaz, az enum-listák a 192., 202. és
446. sorban vannak):

```
192:          enum: ["cic-mcp-session", "cic-mcp-shared", "cic-mcp-knowledge", "cic-mcp-workdir"]
202:          enum: ["session_local", "session_derived", "shared_mixed", "canonical", "workdir_local"]
446:          enum: ["cic-mcp-session", "cic-mcp-shared", "cic-mcp-knowledge", "cic-mcp-workdir"]
```

- 192. sor: `sources_used[].source_id` enum (4 érték)
- 202. sor: `sources_used[].trust_domain` enum (5 érték)
- 446. sor: `refs[].source_id` enum (ugyanaz a 4 érték, másik mezőn)

**Side-by-side összevetés a saját `gateway-source-registry.schema.yaml`-lal**
(`python3 -c "import yaml; ..."` paranccsal kiolvasva a betöltött struktúrából):

| Enum | `gateway-context-envelope.schema.yaml` (192/202. sor) | `gateway-source-registry.schema.yaml` (`properties.source_id`/`trust_domain`) | Egyezés |
|---|---|---|---|
| `source_id` | `["cic-mcp-session", "cic-mcp-shared", "cic-mcp-knowledge", "cic-mcp-workdir"]` | `["cic-mcp-session", "cic-mcp-shared", "cic-mcp-knowledge", "cic-mcp-workdir"]` | igen, szó szerint |
| `trust_domain` | `["session_local", "session_derived", "shared_mixed", "canonical", "workdir_local"]` | `["session_local", "session_derived", "shared_mixed", "canonical", "workdir_local"]` | igen, szó szerint |

**Eredmény: nincs eltérés.** A saját schema PONTOSAN ugyanazt a 4 `source_id`
és 5 `trust_domain` enum-értéket használja, mint a már mergelt
`gateway-context-envelope.schema.yaml`. Nincs kontraktus-törés, nincs csendes
módosítás.

## Schema Summary

A `output/gateway-source-registry.schema.yaml` az `apiVersion`/`kind`/
`metadata`/`required`/`properties` konvenciót követi (azonos a
`GatewayContextEnvelope` és a `SessionIngressEnvelope` mintájával), kiegészítve
egy `invariants` és egy `forbidden_combinations` blokkal (ugyanaz a mintázat,
mint a `gateway-context-envelope.schema.yaml`-ban).

**Top-level required mezők (6, egy registry-bejegyzésre):** `source_id`,
`trust_domain`, `owns_raw_storage`, `returns_trust_envelope`,
`query_capabilities`, `canonical` — pontosan a job-spec 2. lépésében felsorolt
6 mező, kiegészítés nélkül (a `gateway-baseline.md` "Source Registry — Initial
Boundary" táblájának teljes mezőlistája).

Kiegészítő blokkok:
- `invariants` (3 tétel): az enum-szinkron kényszer, a "registry nem a
  gateway saját bejegyzése" szabály, és a "`canonical: true` csak
  `cic-mcp-knowledge`-re" szabály
- `forbidden_combinations` (5 tétel): hiányzó `trust_domain`, nem-knowledge
  `canonical: true`, gateway-önbejegyzés, üres `query_capabilities`, és
  enum-eltérés a `gateway-context-envelope.schema.yaml`-tól

A schema kifejezetten **per-entry** kontraktus (egy registry-bejegyzés alakja),
nem a teljes registry-lista wrapper-sémája — ez konzisztens azzal, hogy a
`gateway-baseline.md` "Source Registry — Initial Boundary" táblája is
mező-szintű leírást ad egy bejegyzésre, nem egy lista-wrapper objektumra.

## cic-mcp-workdir vs cic-factory Decision

**Döntés: a `cic-mcp-workdir` ÖNÁLLÓ, KÜLÖN source-domain a registry-ben —
NEM egy `cic-factory`-proxy-bejegyzés.**

Indoklás, konkrét forrás-sorokra hivatkozva:

1. **`docs/en/architecture.md` 19. sor** (a komponens-térkép szöveges
   diagramja): `cic-mcp-workdir     current repo/worktree/branch/diff (role
   filled by cic-factory)`. Ez a sor **`cic-mcp-workdir`-t nevezi a
   source-domain-nak**, a `cic-factory`-t pedig zárójelben, mint annak
   *jelenlegi implementációs szerepét* ("role filled by") — NEM mint a
   registry-bejegyzés saját azonosítóját. A "role filled by X" megfogalmazás
   nyelvtanilag azt jelenti, hogy van egy fogalmi pozíció (`cic-mcp-workdir`),
   amit jelenleg egy konkrét komponens (`cic-factory`) tölt be — nem azt, hogy
   a pozíció maga `cic-factory` lenne.
2. **`docs/en/architecture.md` 23. sor**, UGYANEBBEN a diagramban:
   `cic-mcp-factory     the family's capability production/maintenance
   factory`. A `cic-mcp-factory` **külön sorként** szerepel, MÁS leírással
   (capability-gyártás/karbantartás, nem repo/worktree/branch/diff állapot) —
   ha a registry-ben `cic-mcp-workdir` helyett egyszerűen `cic-mcp-factory`
   szerepelne, az összemosná két, a diagramban explicit elkülönített
   fogalmi szerepet (forrás-domain vs. family-szintű gyártósor).
3. **`cic-mcp-factory/.cic-context/factory-docs/architecture.md` 15-16. sor**:
   `cic-mcp-workdir` saját, önálló sorként szerepel a normatív komponens-
   térképben is (`aktuális repo/worktree/branch/diff/állapot`), a `cic-factory`
   sora pedig külön szövegként jelenik meg ("MCP capability-k gyártó és
   karbantartó factory-ja") — ez a normatív (nem gateway-specifikus kivonat)
   forrás is megerősíti az 1-2. pontot.
4. **Konzisztencia a `gateway-context-envelope.schema.yaml`-lal**: a
   `sources_used[].source_id` enum MÁR rögzíti a `cic-mcp-workdir` értéket
   (192. sor) — ha ez a job a registry-ben `cic-factory`-proxy-bejegyzést
   hozott volna létre `cic-mcp-workdir` helyett, az egy `source_id` érték
   nélküli registry-bejegyzést eredményezett volna a MÁR mergelt envelope
   schema enum-jában rögzített értékhez, ami közvetlen kontraktus-ellentmondás
   lenne. A döntés (önálló `cic-mcp-workdir` bejegyzés) ELKERÜLI ezt az
   ellentmondást, mert pontosan azt az enum-értéket veszi fel registry-
   bejegyzésnek, amit az envelope schema már elvár.

**A "látszólagos ellentmondás" explicit feloldása** (a job-spec 3. pontja
megköveteli ezt, ha talált ilyet): a `gateway-baseline.md` "Risks" szekciójának
harmadik tétele nyitva hagyta a kérdést, mert a `cic-factory` JELENLEG
*betölti* a `cic-mcp-workdir` szerepét (nincs még önálló `cic-mcp-workdir`
repo/implementáció — ez `concept`/`scaffold` státuszú, nem `implemented`). Ez
NEM jelenti azt, hogy a registry-bejegyzésnek `cic-factory`-t kellene
azonosítóként használnia — a registry-bejegyzés a **fogalmi source-domain-t**
azonosítja (`cic-mcp-workdir`), nem azt, MELYIK komponens szolgálja ki jelenleg
a kéréseket. Ez pontosan analóg azzal, hogy egy jövőbeli
`gateway-session-adapter-contract-001` implementáció is a `cic-mcp-session`
source_id alatt regisztrálódna, függetlenül attól, hogy az adaptert melyik
konkrét kódbázis futtatja.

**Státusz-megjegyzés**: a `cic-mcp-workdir` mint source_id jelenleg
`concept`/`scaffold` státuszú a háromszintű státusz-modell szerint — a
registry-bejegyzés LÉTEZIK schema-szinten (ez a job), de nincs hozzá önálló
`cic-mcp-workdir` repo vagy futó adapter; a tényleges lekérdezéseket jelenleg
a `cic-factory` szolgálja ki "proxy módon", DE ez egy implementációs tény, nem
registry-szerkezeti döntés. Ha a jövőben létrejön egy önálló `cic-mcp-workdir`
repo, a registry-bejegyzés VÁLTOZATLAN marad (`source_id: cic-mcp-workdir`) —
csak a mögötte álló implementáció cserélődik, ami pontosan az a
entkopplázás, amit egy registry-kontraktusnak biztosítania kell.

## Findings

1. A `gateway-context-envelope.schema.yaml` `source_id`/`trust_domain` enum-jai
   (192/202/446. sor) PONTOSAN megegyeznek a `gateway-baseline.md` "Source
   Registry — Initial Boundary" YAML-vázlatában felsorolt 4 source-bejegyzés
   `source_id`/`trust_domain` párjaival — nincs olyan eltérés, amit jelezni
   kellene a két KORÁBBI dokumentum között.
2. A job-spec 2. lépésében megadott 6 mező (`source_id`, `trust_domain`,
   `owns_raw_storage`, `returns_trust_envelope`, `query_capabilities`,
   `canonical`) szó szerint megegyezik a `gateway-baseline.md` "Source
   Registry — Initial Boundary" mezőlista-táblájával — a schema nem hagyott ki
   és nem adott hozzá domain-mezőt, csak a stílus-konvenció keretét
   (`apiVersion`/`kind`/`metadata`).
3. A `query_capabilities` mezőt `minItems: 1`-gyel kényszerítettem ki (nem
   `minItems: 0`) — egy regisztrált forrás, amely semmilyen query-típust nem
   tud kiszolgálni, route-olhatatlan célpont, ezt explicit `forbidden_combinations`
   tételként is rögzítettem (`forbidden-empty-query-capabilities`).
4. A `canonical: true` mezőt `cic-mcp-knowledge`-re korlátoztam dokumentált
   (nem schema-szinten kikényszerített) invariánsként — ugyanaz a minta, mint
   a `gateway-context-envelope.schema.yaml` `forbidden-canonical-promotion-by-gateway`
   tétele, csak registry-szinten, korábban a pipeline-ban.
5. A `cic-mcp-workdir`/`cic-factory` kérdés MÁR az envelope schema enum-jában
   (192. sor) implicit eldöntött volt — ez a job ezt explicitté tette és
   forrás-hivatkozással alátámasztotta, nem egy új döntést hozott a nulláról.
6. A schema `invariants`/`forbidden_combinations` blokkjai dokumentációs
   jellegűek, NINCS futtatható validátor — ahogy az input.md előírja (lásd
   "Rejected / Out Of Scope").

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| A `gateway-context-envelope.schema.yaml` `source_id` enum-ja 4 értéket tartalmaz: `cic-mcp-session`, `cic-mcp-shared`, `cic-mcp-knowledge`, `cic-mcp-workdir` | proven | grep-kimenet 192. sor: `enum: ["cic-mcp-session", "cic-mcp-shared", "cic-mcp-knowledge", "cic-mcp-workdir"]` (lásd "Enum Sync Check") | grep futtatva, kimenet szó szerint idézve | low |
| A `gateway-context-envelope.schema.yaml` `trust_domain` enum-ja 5 értéket tartalmaz: `session_local`, `session_derived`, `shared_mixed`, `canonical`, `workdir_local` | proven | grep-kimenet 202. sor: `enum: ["session_local", "session_derived", "shared_mixed", "canonical", "workdir_local"]` | grep futtatva, kimenet szó szerint idézve | low |
| A saját `gateway-source-registry.schema.yaml` `source_id`/`trust_domain` enum-ja PONTOSAN egyezik a fenti két enummal | proven | `python3 -c "import yaml; ..."` kimenete: `source_id enum: ['cic-mcp-session', 'cic-mcp-shared', 'cic-mcp-knowledge', 'cic-mcp-workdir']`, `trust_domain enum: ['session_local', 'session_derived', 'shared_mixed', 'canonical', 'workdir_local']` — side-by-side tábla a "Enum Sync Check" szekcióban | yaml.safe_load futtatva, kimenet idézve | low |
| A `gateway-source-registry.schema.yaml` YAML-szintaktikailag valid | proven | `python3 -c "import yaml; yaml.safe_load(open('output/gateway-source-registry.schema.yaml'))"` hibamentesen futott, kiírta a top-level kulcsokat (`apiVersion, kind, metadata, invariants, required, properties, forbidden_combinations`), a `required` 6 mezőjét és a `properties` 6 kulcsát | parancs futtatva, kimenet idézve | low |
| A schema a job-spec 2. lépésében megadott pontosan 6 mezőt tartalmazza | proven | `required: ['source_id', 'trust_domain', 'owns_raw_storage', 'returns_trust_envelope', 'query_capabilities', 'canonical']` — yaml.safe_load kimenete | parancs futtatva, kimenet idézve | low |
| A `cic-mcp-workdir` önálló source-domain a registry-ben, nem `cic-factory`-proxy | proven | `docs/en/architecture.md` 19. és 23. sor szó szerint idézve ("cic-mcp-workdir current repo/worktree/branch/diff (role filled by cic-factory)" vs. "cic-mcp-factory the family's capability production/maintenance factory" — két külön sor) + `cic-mcp-factory/.cic-context/factory-docs/architecture.md` 15-16. sor megerősítve | fájl-tartalom idézve, két független forrásból | low |
| A döntés konzisztens a már mergelt `gateway-context-envelope.schema.yaml` enum-jával | proven | a 192. sor enum-ja MÁR tartalmazza `cic-mcp-workdir`-t mint `source_id` értéket — a registry-döntés ugyanezt az értéket veszi fel, nincs ellentmondás (lásd "cic-mcp-workdir vs cic-factory Decision" 4. pontja) | enum-érték keresztreferencia | low |
| A report legalább 4 valid + 2 invalid registry-bejegyzést tartalmaz indoklással | proven | lásd "Valid Registry Entries" (4 db, egy minden ismert `source_id`-ra) + "Invalid Registry Entries" (3 db, mindegyiknél explicit "Miért invalid" alszekció) | jelen dokumentum tartalma | low |
| Nincs futtatható registry betöltő/validátor kód a job kimenetében | proven | `git status`/`git diff --stat` a commit előtt csak `output/gateway-source-registry-contract.md` és `output/gateway-source-registry.schema.yaml` új fájlokat mutatja, nincs `.py`/végrehajtható fájl | git diff futtatva commit előtt | low |

## Valid Registry Entries

### Valid Entry 1 — `cic-mcp-knowledge` (canonical layer)

```yaml
source_id: "cic-mcp-knowledge"
trust_domain: "canonical"
owns_raw_storage: true
returns_trust_envelope: false
query_capabilities: ["full_text", "vector", "graph"]
canonical: true
```

**Miért valid:** minden `required` mező jelen van; `canonical: true` itt
LEGITIM, mert `source_id` pontosan `cic-mcp-knowledge` (az egyetlen forrás,
amire ez engedélyezett az invariáns `registry-canonical-true-only-for-knowledge-layer`
szerint); `owns_raw_storage: true` LEGITIM, mert ez a FORRÁS saját tárolási
tényét állítja (cic-mcp-knowledge saját canonical store-ja), nem a gateway-ét;
`query_capabilities` nem-üres lista.

### Valid Entry 2 — `cic-mcp-session` (session-local layer)

```yaml
source_id: "cic-mcp-session"
trust_domain: "session_local"
owns_raw_storage: true
returns_trust_envelope: false
query_capabilities: ["timeline", "vector", "full_text"]
canonical: false
```

**Miért valid:** `trust_domain: "session_local"` az enum egyik tagja;
`canonical: false` — a session réteg sosem canonical alapból (a
`gateway-context-envelope.schema.yaml` `session_derived_notes.trust` enum-ja
is csak `session_local`/`session_derived`-et enged, sosem `canonical`-t, ami
megerősíti ezt a bejegyzést); `owns_raw_storage: true` LEGITIM forrás-szintű
állítás (cic-mcp-session saját raw event store-ja).

### Valid Entry 3 — `cic-mcp-shared` (shared/mixed layer)

```yaml
source_id: "cic-mcp-shared"
trust_domain: "shared_mixed"
owns_raw_storage: false
returns_trust_envelope: false
query_capabilities: ["graph", "full_text"]
canonical: false
```

**Miért valid:** `owns_raw_storage: false` itt is LEGITIM (nem minden forrásnak
kell `true`-nak lennie — a `cic-mcp-shared` aggregált/derivált adatot tart,
nem elsődleges raw ingestion-t, lásd `cic-mcp-factory/.cic-context/factory-docs/architecture.md`
"cic-mcp-shared" Nem-lista: "raw hook ingestion első igazságforrása" — explicit
NEM a `cic-mcp-shared` felelőssége); `canonical: false`, mert a shared
réteg "not canonical by default even when reviewed_shared"
(`gateway-context-envelope.schema.yaml` `shared_memory_notes.trust`
description).

### Valid Entry 4 — `cic-mcp-workdir` (workdir-local layer, role currently filled by cic-factory)

```yaml
source_id: "cic-mcp-workdir"
trust_domain: "workdir_local"
owns_raw_storage: false
returns_trust_envelope: false
query_capabilities: ["repo_diff", "branch_state"]
canonical: false
```

**Miért valid:** `source_id: "cic-mcp-workdir"` — a "cic-mcp-workdir vs
cic-factory Decision" szekció szerint ez az önálló, helyes source-domain
azonosító, NEM `cic-factory`; `owns_raw_storage: false`, mert a
repo/worktree/branch/diff állapot maga a git/filesystem állapota, nem egy
külön raw-storage réteg, amit a "forrás" maga tartana fenn (ezt a gateway
szempontjából egy másik komponens, jelenleg `cic-factory`, olvassa ki és
szolgáltatja); `query_capabilities` egy egyszerű, workdir-specifikus
kapacitáslista (`repo_diff`, `branch_state`) — ezek illusztratívak, a tényleges
kapacitás-taxonómiát egy jövőbeli adapter-job rögzítheti pontosabban.

## Invalid Registry Entries

### Invalid Entry 1 — hiányzó `trust_domain`

```yaml
source_id: "cic-mcp-session"
owns_raw_storage: true
returns_trust_envelope: false
query_capabilities: ["timeline"]
canonical: false
```

**Miért invalid:** a `trust_domain` kulcs teljesen hiányzik. A schema
`required` listája tartalmazza a `trust_domain`-t — ez pontosan a
`forbidden-missing-trust-domain` tétel esete: egy `source_id` nélküli
`trust_domain` deklaráció nélkül a gateway nem tudja eldönteni, milyen
trust-szintet kell a forrásból érkező adatra ragasztania, ami megakadályozza
a "trust-domain source routing" felelősség (architecture.md "Igen" lista)
teljesítését.

### Invalid Entry 2 — `cic-mcp-shared`-en `canonical: true`

```yaml
source_id: "cic-mcp-shared"
trust_domain: "shared_mixed"
owns_raw_storage: false
returns_trust_envelope: false
query_capabilities: ["graph"]
canonical: true
```

**Miért invalid:** `canonical: true` egy olyan source_id-n
(`cic-mcp-shared`), ami NEM `cic-mcp-knowledge` — ez a
`forbidden-non-knowledge-canonical-true` tétel megsértése. A
`gateway-baseline.md` "Source Registry — Initial Boundary" táblája explicit
kimondja: "canonical | bool | a forrás tartalma canonical-e (alapból csak
`cic-mcp-knowledge` review után)". Ha ez a bejegyzés érvényes lenne, a
gateway egy aggregált, nem-review-zott shared-tartalmat canonical-ként
kezelhetne, ami megsértené a `gateway-does-not-create-truth` invariánst már a
registry szintjén — mielőtt bármilyen tényleges query lefutna.

### Invalid Entry 3 — gateway-önbejegyzés `owns_raw_storage: true`-val

```yaml
source_id: "cic-mcp-gateway"
trust_domain: "canonical"
owns_raw_storage: true
returns_trust_envelope: true
query_capabilities: ["full_text"]
canonical: true
```

**Miért invalid:** kettős hiba. (1) `source_id: "cic-mcp-gateway"` NEM tagja
a rögzített `source_id` enum-nak (`cic-mcp-session`, `cic-mcp-shared`,
`cic-mcp-knowledge`, `cic-mcp-workdir`) — a gateway sosem regisztrálja saját
magát forrásként, ez a `forbidden-gateway-self-entry` tétel esete. (2) Még ha
az enum megengedné, `owns_raw_storage: true` és `canonical: true` egy
gateway-bejegyzésen direkt ellentmondana a gateway saját, MÁR rögzített trust
modelljének (`architecture.md`: `owns_raw_storage: false`,
`owns_embedding_store: false`) — a gateway sosem tárol raw adatot és sosem
canonical forrás, ez axiomatikus determináció, nem regisztrálható bejegyzés
kérdése.

## Decisions Proposed

1. **A `cic-mcp-workdir` ÖNÁLLÓ source-domain a registry-ben, a `cic-factory`
   csak a JELENLEGI implementációs szerepét tölti be.** Javaslat: minden
   jövőbeli gateway-job (kiemelten egy jövőbeli `gateway-workdir-adapter-contract-001`,
   ha lesz) `source_id: cic-mcp-workdir`-t használjon, ne `cic-factory`-t —
   ez biztosítja, hogy a registry-bejegyzés stabil maradjon akkor is, ha a
   mögötte álló implementáció (`cic-factory` → egy önálló `cic-mcp-workdir`
   repo) idővel cserélődik.
2. **A `query_capabilities` `minItems: 1` kényszer bevezetése** — egy
   registrált forrásnak legalább egy lekérdezési képességet kötelezően
   deklarálnia kell, különben route-olhatatlan; ha egy forrás ideiglenesen
   nem kínál semmilyen kapacitást, ki kell vezetni a registry-ből, nem
   üres listával benne tartani.
3. **A `canonical: true` registry-szintű korlátozása `cic-mcp-knowledge`-re,
   dokumentált (nem schema-kikényszerített) invariánsként** — javaslat:
   bármely jövőbeli validátor-implementáció (ha lesz, egy külön jobban) ezt
   az invariánst kódolja le elsőként, mert ez korábban a pipeline-ban
   blokkolja a canonical-laundering kockázatot, mint az envelope-szintű
   `forbidden-canonical-promotion-by-gateway` szabály.
4. **A registry-schema `source_id`/`trust_domain` enum-jainak a
   `gateway-context-envelope.schema.yaml`-lal való szinkronban tartása
   explicit követelmény minden jövőbeli patch-re** — ha bármelyik schema
   enum-ja bővül, a másikat is egy koordinált patch jobban kell frissíteni,
   nem külön-külön, eltérő ütemben.

## Rejected / Out Of Scope

- **Registry betöltő/validátor FUTTATHATÓ kódjának megírása** — explicit
  kizárva (input.md "Nem cél" 1. pont); a `forbidden_combinations` blokk 4
  tétele emiatt dokumentált, de NEM schema-szinten kikényszerített.
- **`GatewayContextEnvelope` schema MÓDOSÍTÁSA** — nem történt; az "Enum Sync
  Check" szekció bizonyítja, hogy nem is volt rá szükség (nincs eltérés). A
  `gateway-context-envelope.schema.yaml` fájl ebben a jobban kizárólag
  OLVASÁSRA került.
- **Tényleges routing logika vagy adapter kód** (`gateway-session-adapter-contract-001`
  és társai) — explicit kizárva (input.md "Nem cél" 3. pont); ez egy jövőbeli
  job feladata.
- **`cic-mcp-session`/`cic-mcp-shared`/`cic-mcp-knowledge`/`cic-mcp-factory`
  repók módosítása** — nem történt, nem is volt indokolt; ezek a repók nem is
  voltak klónozva ehhez a jobhoz (a workplace csak `cic-mcp-factory` és
  `cic-mcp-gateway`-t tartalmazta).
- **A `query_capabilities` taxonómia teljes, végleges definíciója** — a
  schema csak `list[string]`-ként formalizálja a mezőt; egy konkrét, zárt
  enum-taxonómia bevezetése (pl. `full_text`/`vector`/`timeline`/`graph`/...
  zárt listája) egy jövőbeli jobnak való, nem ennek a contract-jobnak (lásd
  "Next Jobs").
- **Egy önálló `cic-mcp-workdir` repo bootstrap-ja vagy implementációja** —
  ez a job kizárólag a registry-bejegyzés azonosítóját (`source_id`) dönti
  el, NEM hoz létre, NEM bootstrapel semmilyen `cic-mcp-workdir` kódbázist.

## Risks

- **Implementáció-helyettesítés félreértés kockázat**: a `cic-mcp-workdir`
  registry-bejegyzés mögött JELENLEG nincs önálló kódbázis — a `cic-factory`
  szolgálja ki ezeket a lekérdezéseket. Ha egy jövőbeli adapter-job ezt
  figyelmen kívül hagyva direkt a `cic-factory` belső API-jára hardcode-ol,
  elveszik a registry-bejegyzés entkapszuláló célja. Mitigáció: ez a report
  explicit kimondja a "cic-mcp-workdir vs cic-factory Decision" szekcióban,
  hogy a `source_id: cic-mcp-workdir` FÜGGETLEN a mögötte álló implementációtól.
- **`query_capabilities` szabad-szöveg kockázat**: jelenleg `list[string]`,
  nincs zárt enum — ez lehetővé teszi, hogy két jövőbeli registry-bejegyzés
  inkonzisztens kapacitás-string formátumot használjon (pl. `"full_text"` vs.
  `"fulltext"`). Mitigáció: explicit Out Of Scope-ként rögzítve, javaslat egy
  követő taxonómia-jobra (lásd Next Jobs), ugyanaz a minta, mint a
  `query_intent` szabad-szöveg kockázat volt a `gateway-context-envelope-contract-001`
  jobban.
- **Cross-schema enum-drift kockázat**: a két schema (`gateway-context-envelope.schema.yaml`
  és `gateway-source-registry.schema.yaml`) enum-szinkronja jelenleg KIZÁRÓLAG
  ennek a reportnak a manuális grep/side-by-side ellenőrzésével biztosított,
  nincs automatizált cross-schema validáció. Egy jövőbeli patch, amely csak az
  egyik fájlt módosítja, csendben szétcsúszhat. Mitigáció: a
  `forbidden-source-id-trust-domain-enum-drift` tétel explicit dokumentálja
  ezt a kockázatot a schema-fájlban is, nem csak a reportban.
- **`query_capabilities`/`query_capability_used` cross-field konzisztencia
  kockázat**: a `gateway-context-envelope.schema.yaml` `query_capability_used`
  mezőjének (egy konkrét lekérdezésben tényleg használt kapacitás) konzisztensnek
  kellene lennie a regisztrált forrás `query_capabilities` listájával — ez
  jelenleg dokumentált, de nincs validátor, ami ellenőrizné, hogy egy
  envelope-ban szereplő `query_capability_used` valóban szerepel-e a forrás
  regisztrált listájában. Mitigáció: jövőbeli validátor-job feladata (lásd
  Next Jobs).

## Definition Of Done Check

- [x] `source_id`/`trust_domain` enum-ok PONTOSAN egyeznek a
      `gateway-context-envelope.schema.yaml`-jal, side-by-side idézve
      → lásd "Enum Sync Check" szekció, grep-kimenet + side-by-side tábla
- [x] `cic-mcp-workdir` vs `cic-factory` kérdés lezárva, döntéssel és
      forrás-hivatkozással
      → lásd "cic-mcp-workdir vs cic-factory Decision" szekció, 4 konkrét
      forrás-sorra hivatkozva (docs/en/architecture.md 19/23. sor,
      factory-docs/architecture.md 15-16. sor, envelope schema 192. sor)
- [x] legalább 4 valid + 2 invalid registry-bejegyzés, indoklással
      → 4 valid (egy minden ismert `source_id`-ra) + 3 invalid (a job-spec
      minimumánál egy extrával, a gateway-önbejegyzés tilalmának
      illusztrálására), mindegyik invalid-nál explicit "Miért invalid"
      alszekció
- [x] claim-evidence tábla kitöltve, nem üres
      → 9 sor, mind `proven` státusszal, fájl-idézettel/parancs-kimenettel
      alátámasztva

## Next Jobs

1. **`gateway-session-adapter-contract-001`** (a `gateway-context-envelope-contract-001`
   report "Next Jobs" 2. pontjában már javasolt) — most, hogy a source
   registry kontraktusa is rögzült, ez az első konkrét adapter-job, amely
   tényleg előállít egy `GatewayContextEnvelope` instance-t `cic-mcp-session`
   forrásból, ÉS amelynek a `cic-mcp-session` registry-bejegyzését (`source_id:
   cic-mcp-session`, `query_capabilities`) is ehhez a schema-hoz kell
   igazítania. Ez lesz az első valódi teszt arra, hogy a registry mezői
   gyakorlatban elegendőek-e (`candidate` promócióhoz ez kell, a Target
   szekció "status indoklás" szerint).
2. **(opcionális, alacsony prioritású) `gateway-query-capability-taxonomy-001`**
   — jelen schema-revízióban `query_capabilities` szabad `list[string]`; ha az
   adapter-job(ok) tapasztalata azt mutatja, hogy konkrét zárt enum/taxonómia
   kell, egy külön job formalizálja, NEM ez a job (lásd "Rejected / Out Of
   Scope").
3. **(opcionális, alacsony prioritású) `gateway-registry-validator-001`** —
   egy jövőbeli job, amely az itt dokumentált (de nem kikényszerített)
   `invariants`/`forbidden_combinations` tételekből (pl.
   `forbidden-non-knowledge-canonical-true`,
   `forbidden-source-id-trust-domain-enum-drift`) tényleges, futtatható
   validátor-logikát generál — explicit ennek a jobnak a hatókörén kívül
   (lásd "Nem cél"), de a schema kommentjei előkészítik a talajt neki.
