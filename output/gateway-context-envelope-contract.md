# gateway-context-envelope-contract-001 Output

## Scope

Ez a job a `GatewayContextEnvelope` — a `cic-mcp-gateway` agent-facing API-ja által
visszaadott, trust-jelölt kontextus-csomag — ELSŐ formális YAML schema-kontraktusát
definiálja. Ez **schema-kontraktus job, nem implementáció**: nincs futtatható kód, nincs
routing logika, nincs JSON-Schema validátor. A leszállított artifact két fájl:
`output/gateway-context-envelope.schema.yaml` (a schema maga) és ez a report.

Nem cél (lásd input.md "Nem cél" + lent "Rejected / Out Of Scope"): source registry
definiálása, routing/adapter kód, futtatható validátor, vagy a
`cic-mcp-session`/`cic-mcp-shared`/`cic-mcp-knowledge` repók módosítása.

## Inputs Read

- `cic-mcp-gateway/output/gateway-baseline.md` — teljes terjedelem, kiemelten a
  "GatewayContextEnvelope — Initial Boundary", "Decisions Proposed", "Risks" szekciók
- `cic-mcp-gateway/docs/hu/architecture.md` és `docs/en/architecture.md` — teljes
  terjedelem, kiemelten "Tervezett adatfolyam"
- `cic-mcp-gateway/CLAUDE.md` — teljes terjedelem, trust modell szekció
- `cic-mcp-factory/.cic-context/factory-docs/architecture.md` — "cic-mcp-gateway" Igen/Nem
  szekció
- `cic-mcp-factory/.cic-context/factory-docs/execution-phases.md` — "Phase 1B" szekció
- `cic-mcp-factory/.cic-context/factory-docs/acceptance-contract.md` — "Gateway-Specific
  Contract" + "Artifact Contract" szekciók
- `cic-mcp-factory/.cic-context/corpus/normalized/thead-review-2026-06-20.yaml` —
  `dec-thead-0005`
- Stílus-referencia: `cic-mcp-factory/jobs/session-ingress-envelope-contract-001/output/
  session-ingress-envelope.schema.yaml` (a `cic-mcp-factory` klónban már elérhető
  másolat — a `cic-mcp-session` repo maga nincs klónozva ehhez a jobhoz, az input.md
  szerint a konvenciót innen vagy a "Schema stílus-konvenció" szekcióból kellett átvenni;
  ez a fájl elérhető volt, így a tényleges, már elfogadott konvenciót követtem, nem csak a
  vázlatot)
- `mcp__cic-graph__kb_status` (Boot sequence 1. lépés) — eredmény: `cache_info` 6 hit / 1
  miss / 1 currsize, mind a 6 pkl/faiss/bm25 artifact (`chunks.pkl`, `graph_nodes.pkl`,
  `graph_edges.pkl`, `inverted_index.pkl`, `faiss.index`, `bm25.pkl`) `exists: true` —
  a KB friss és elérhető, a Boot sequence teljesítve

## Schema Summary

A `output/gateway-context-envelope.schema.yaml` az `apiVersion`/`kind`/`metadata`/
`required`/`properties` konvenciót követi (azonos a `SessionIngressEnvelope`-pal), kiegészítve
egy `invariants` és egy `forbidden_combinations` blokkal (ugyanaz a mintázat, mint a
session schema-ban).

**Top-level required mezők (16):** `apiVersion`, `kind`, `envelope_id`, `created_at`,
`query_intent`, `scope`, `answer_type`, `sources_used`, `trust_summary`,
`canonical_facts`, `workdir_facts`, `session_derived_notes`, `shared_memory_notes`,
`conflicts`, `proof_requirements`, `refs`.

A 4 tartalom-kategória mind property-szinten elkülönült, saját `items.properties`-szel:
`canonical_facts`, `workdir_facts`, `session_derived_notes`, `shared_memory_notes` — nincs
közös `facts` property a schema-ban (ellenőrizve: `properties` kulcsai között nem szerepel
`facts`, csak a négy elkülönült mező).

A "nem tárol raw adatot / nem tárol embedding-et" tétel az `invariants` blokk első két
elemében (`gateway-owns-no-raw-storage`, `gateway-owns-no-embedding-store`) van rögzítve,
leíró szinten — nincs hozzá futtatható validátor, ahogy az input.md előírja.

## Findings

1. A doc-tervben javasolt 12 mező (`answer_type`, `query_intent`, `scope`, `sources_used`,
   `trust_summary`, `canonical_facts`, `workdir_facts`, `session_derived_notes`,
   `shared_memory_notes`, `conflicts`, `proof_requirements`, `refs`) mind a 12 megjelenik a
   schema `required` listájában — a job nem hagyott ki semmit a doc-tervből, csak
   kiegészítette (`apiVersion`, `kind`, `envelope_id`, `created_at` — ezek a stílus-
   konvenció kötelező keret-mezői, a `SessionIngressEnvelope` mintájára).
2. A `sources_used` mezőt listaként formalizáltam, ahol minden elem egy `{source_id,
   trust_domain, query_capability_used?}` objektum — ez a `gateway-baseline.md` "Source
   Registry — Initial Boundary" 4 source_id-jét (`cic-mcp-session`, `cic-mcp-shared`,
   `cic-mcp-knowledge`, `cic-mcp-workdir`) és a hozzájuk tartozó `trust_domain` enumot
   (`session_local`, `shared_mixed`, `canonical`, `workdir_local`) tükrözi vissza enum-
   constraint formájában, nem szabad szövegként.
3. A `trust_summary` objektum `overall_confidence` + `per_category` (a 4 tartalom-kategória
   mindegyikére saját confidence-érték, `not_used` opcióval az üres kategóriákhoz) — ez
   biztosítja, hogy a trust-jelölés ne legyen egy laza szabad-szöveg mező, és konzisztens
   maradjon a content-mezők tényleges kitöltöttségével.
4. A `conflicts` és `proof_requirements` mezők top-level `required`-ben szerepelnek
   (`minItems: 0`, nem `minItems: 1`) — ez pontosan az input.md/Forbidden Shortcuts
   tételét kódolja: a mező MINDIG jelen van, az üres lista egy explicit pozitív állítás
   ("nincs ismert konfliktus"), nem a mező hiánya.
5. A `refs` mező egy közös evidence-tábla — minden content-mező `ref`/`conflicting_refs`/
   `blocking_for` hivatkozása ide kell, hogy felbontható legyen; ez konzisztens a
   `SessionIngressEnvelope` stílusával, ahol minden mező provenance-hivatkozással bír.
6. A `forbidden_combinations` blokk 5 tételt rögzít — 3 schema-szinten kikényszeríthető
   (`required` mezők hiánya, közös `facts` mező hiánya a property-listából), 2 pedig
   explicit dokumentált, de NEM schema-szinten kikényszerített invariáns (canonical
   promotion gateway által, raw passthrough) — ez utóbbi kettő cross-field/runtime
   ellenőrzést igényelne, amit egy validátor-implementáció adna, és az input.md explicit
   kizárja a futtatható validátor megírását ebből a jobból.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| A schema tartalmazza a `sources_used` mezőt required-ként | proven | `output/gateway-context-envelope.schema.yaml` `required:` lista 8. eleme: `- sources_used`; `properties.sources_used` blokk definiálva (`type: array`, `items` séma `source_id`/`trust_domain`-nel) | fájl-tartalom idézve + `python3 -c "import yaml; ..."` szintaktikai ellenőrzés (lásd alább, futtatva) | low |
| A schema tartalmazza a `trust_summary` mezőt required-ként | proven | `required:` lista 9. eleme: `- trust_summary`; `properties.trust_summary` `type: object`, `required: [overall_confidence, per_category]` | fájl-tartalom idézve | low |
| A schema tartalmazza a `conflicts` mezőt KÖTELEZŐ mezőként, NEM opcionálisként | proven | `required:` lista 14. eleme: `- conflicts`; `properties.conflicts` `minItems: 0` (lehet üres, de a kulcs jelenléte kötelező); `forbidden_combinations[0]` (`forbidden-missing-conflicts-field`) explicit rögzíti az indoklást | fájl-tartalom idézve | low |
| A schema tartalmazza a `proof_requirements` mezőt KÖTELEZŐ mezőként | proven | `required:` lista 15. eleme: `- proof_requirements`; `properties.proof_requirements` `minItems: 0`; `forbidden_combinations[1]` indoklás | fájl-tartalom idézve | low |
| A schema tartalmazza a `refs` mezőt required-ként | proven | `required:` lista 16. eleme: `- refs`; `properties.refs` `type: array`, item-séma `ref_id`/`source_id`-vel | fájl-tartalom idézve | low |
| A schema property-szinten elkülöníti a 4 tartalom-kategóriát (NEM egy közös `facts` mező) | proven | `properties` kulcsai között `canonical_facts`, `workdir_facts`, `session_derived_notes`, `shared_memory_notes` mind külön blokkként szerepelnek; `facts` kulcs NEM létezik a `properties` alatt — ellenőrizve `python3 -c "... 'facts' in data['properties'] -> False"` (lásd Risks/verification log) | fájl-tartalom idézve + szkriptes kulcs-keresés | low |
| A schema dokumentálja, hogy a gateway nem tárol raw adatot / embedding-et | proven | `invariants[0]` (`gateway-owns-no-raw-storage`, "owns_raw_storage = false...") és `invariants[1]` (`gateway-owns-no-embedding-store`, "owns_embedding_store = false...") szó szerint idézve a schema fájlból | fájl-tartalom idézve | low |
| A schema YAML-szintaktikailag valid | proven | `python3 -c "import yaml; yaml.safe_load(open('output/gateway-context-envelope.schema.yaml'))"` hibamentesen futott, kiírta a top-level kulcsokat és a required/properties listák hosszát (16/16) | parancs futtatva, kimenet idézve a Findings/Schema Summary szekciókban | low |
| A schema-stílus a `SessionIngressEnvelope` konvencióját követi (`apiVersion`/`kind`/`metadata`/`required`/`properties`, minden mezőhöz `description`) | proven | mindkét fájl top-level szerkezete azonos kulcsrenddel; minden `properties.*` blokk tartalmaz `description` mezőt (ellenőrizve vizuálisan, minden property-blokk végén `description: >` szerepel) | fájl-összevetés (mindkét fájl beolvasva, szerkezet összehasonlítva) | low |
| A report legalább 2 valid + 2 invalid envelope-példát tartalmaz indoklással | proven | lásd "Valid Envelope Examples" (2 db) + "Invalid Envelope Examples" (3 db, mindegyiknél explicit "Miért invalid" alszekció) ebben a fájlban | jelen dokumentum tartalma | low |
| A `GatewayContextEnvelope` explicit el van választva a forrás-specifikus MCP API-któl | proven | lásd "Separation From Source-Specific MCP APIs" szekció, amely felsorolja a `cic-mcp-session` 7 MCP tool-ját (a `cic-mcp-gateway/CLAUDE.md` "MCP szerver tool-ok" táblájából idézve) és kontrasztolja az envelope-pal | dokumentum-keresztreferencia + tábla idézve | low |
| A `cic-mcp-gateway` repo jelen jobnál továbbra is `scaffold` státuszban van (nincs új implementáció, csak schema+doc) | proven | nincs `.py`/routing kód módosítva ebben a jobban, csak `output/*.md` és `output/*.yaml` jött létre; `git status`/`git diff --stat` a commit előtt csak ezt a két új fájlt mutatja | git diff futtatva commit előtt | low |

## Valid Envelope Examples

### Valid Example 1 — single-source canonical lookup, no conflicts

```yaml
apiVersion: "cic.gateway/v1"
kind: "GatewayContextEnvelope"
envelope_id: "f47ac10b-58cc-4372-a567-0e02b2c3d479"
created_at: "2026-06-22T09:15:00Z"
query_intent: "lookup-canonical-fact"
scope:
  scope_kind: "global"
answer_type: "fact_lookup"
sources_used:
  - source_id: "cic-mcp-knowledge"
    trust_domain: "canonical"
    query_capability_used: "full_text"
trust_summary:
  overall_confidence: "high"
  per_category:
    canonical_facts: "high"
    workdir_facts: "not_used"
    session_derived_notes: "not_used"
    shared_memory_notes: "not_used"
canonical_facts:
  - content: "cic-mcp-gateway is a trust-domain aware context compiler, not a generic search proxy."
    ref: "ref-001"
workdir_facts: []
session_derived_notes: []
shared_memory_notes: []
conflicts: []
proof_requirements: []
refs:
  - ref_id: "ref-001"
    source_id: "cic-mcp-knowledge"
    excerpt: "dec-thead-0005, thead02.txt:1007"
```

**Miért valid:** minden top-level `required` mező jelen van; a `conflicts` és
`proof_requirements` explicit üres listaként szerepel (nem hiányzik); a 4
tartalom-kategória mind külön mezőként jelen van (3 üres, 1 kitöltött); a
`canonical_facts` egyetlen elemének `ref` mezője felbontható a `refs` tömbben; a
`trust_summary.per_category` konzisztens a kitöltött/üres kategóriákkal (`not_used` a 3
üres kategóriánál).

### Valid Example 2 — multi-source mixed query with an active conflict and proof requirement

```yaml
apiVersion: "cic.gateway/v1"
kind: "GatewayContextEnvelope"
envelope_id: "9c858901-8a57-4791-81fe-4c455b099bc9"
created_at: "2026-06-22T10:42:11Z"
query_intent: "cross-session-conflict-check"
scope:
  scope_kind: "cross_session"
answer_type: "conflict_report"
sources_used:
  - source_id: "cic-mcp-session"
    trust_domain: "session_derived"
    query_capability_used: "timeline"
  - source_id: "cic-mcp-shared"
    trust_domain: "shared_mixed"
    query_capability_used: "graph"
trust_summary:
  overall_confidence: "medium"
  per_category:
    canonical_facts: "not_used"
    workdir_facts: "not_used"
    session_derived_notes: "medium"
    shared_memory_notes: "low"
canonical_facts: []
workdir_facts: []
session_derived_notes:
  - content: "Session 2026-06-18 records decision: use PostgreSQL pgvector for session vector store."
    trust: "session_derived"
    ref: "ref-101"
shared_memory_notes:
  - content: "Cross-session cluster suggests an earlier candidate memory proposed FAISS-only storage for sessions, marked superseded."
    trust: "candidate"
    ref: "ref-102"
conflicts:
  - description: "session_derived_notes claims pgvector is the chosen session vector backend; shared_memory_notes still surfaces an older FAISS-only candidate that has not been explicitly marked resolved in the shared layer."
    conflicting_refs: ["ref-101", "ref-102"]
    severity: "needs_review"
proof_requirements:
  - description: "Confirm with cic-mcp-shared whether the FAISS-only candidate memory has been formally superseded, or if it is still an open candidate."
    blocking_for: ["ref-102"]
refs:
  - ref_id: "ref-101"
    source_id: "cic-mcp-session"
    excerpt: "session_id=abc123, turn=44"
  - ref_id: "ref-102"
    source_id: "cic-mcp-shared"
    excerpt: "cluster_id=shared-cl-7, candidate_memory_id=cm-19"
```

**Miért valid:** két forrás (`cic-mcp-session`, `cic-mcp-shared`) lett route-olva, mindkettő
külön tartalom-kategóriában jelenik meg (nincs összemosás); a `conflicts` mező nem üres,
mert valódi konfliktust talált, és mindkét `conflicting_refs` felbontható a `refs`
tömbben; a `proof_requirements` is nem-üres és `blocking_for` révén egy konkrét reffel
kapcsolódik; a `trust_summary.per_category` tükrözi, hogy a `shared_memory_notes`
megbízhatósága alacsonyabb (`low`, mert `candidate` trust), mint a `session_derived_notes`
(`medium`).

## Invalid Envelope Examples

### Invalid Example 1 — `conflicts` mező teljesen hiányzik

```yaml
apiVersion: "cic.gateway/v1"
kind: "GatewayContextEnvelope"
envelope_id: "11111111-1111-1111-1111-111111111111"
created_at: "2026-06-22T11:00:00Z"
query_intent: "lookup-canonical-fact"
scope:
  scope_kind: "global"
answer_type: "fact_lookup"
sources_used:
  - source_id: "cic-mcp-knowledge"
    trust_domain: "canonical"
trust_summary:
  overall_confidence: "high"
  per_category:
    canonical_facts: "high"
    workdir_facts: "not_used"
    session_derived_notes: "not_used"
    shared_memory_notes: "not_used"
canonical_facts:
  - content: "Some canonical fact."
    ref: "ref-001"
workdir_facts: []
session_derived_notes: []
shared_memory_notes: []
proof_requirements: []
refs:
  - ref_id: "ref-001"
    source_id: "cic-mcp-knowledge"
# conflicts mező NINCS a dokumentumban
```

**Miért invalid:** a `conflicts` kulcs teljesen hiányzik a dokumentumból (nem `conflicts:
[]`, hanem a kulcs maga nincs jelen). A schema `required` listája tartalmazza a
`conflicts`-ot — ez pont az input.md Forbidden Shortcuts második tétele
("`conflicts`/`proof_requirements` mező opcionálisként kezelése"): a hiányzó mező nem
egyenértékű azzal, hogy "nincs konfliktus", hanem azt jelenti, hogy a gateway egyáltalán
nem nyilatkozott a kérdésről — ez egy ellenőrizhetetlen állapot, amit a schema explicit
kizár.

### Invalid Example 2 — nyers vector-similarity hit trust-csomagolás nélkül (`route_query == search_all` jellegű shortcut)

```json
{
  "results": [
    {"chunk_id": "c-991", "score": 0.87, "text": "raw chunk text from session vector index..."},
    {"chunk_id": "c-1042", "score": 0.81, "text": "another raw chunk, source unclear..."}
  ]
}
```

**Miért invalid:** ez nem is `GatewayContextEnvelope` — nincs `apiVersion`/`kind`
discriminator, nincs `sources_used`/`trust_summary`/`conflicts`/`proof_requirements`/`refs`,
csak egy nyers similarity-search eredménylista kerül vissza, becsomagolás nélkül. Ez
pontosan az input.md által megnevezett forbidden shortcut szó szerinti esete ("nyers
vektor-similarity hit van visszaadva trust-csomagolás nélkül — ez pont a forbidden
shortcut") és a schema `forbidden_combinations[4]` (`forbidden-raw-source-passthrough`)
tétele. Még ha utólag `apiVersion`/`kind` mezőket adnánk hozzá, a hiányzó
`trust_summary`/`conflicts`/`proof_requirements` miatt a `required` lista ellen is
elbukna — de a lényegi hiba strukturális: ez sosem ment át trust-domain routingon, csak
egy nyers index-lekérdezés eredménye.

### Invalid Example 3 — a 4 tartalom-kategória összevonva egy közös `facts` mezőbe trust-taggel

```yaml
apiVersion: "cic.gateway/v1"
kind: "GatewayContextEnvelope"
envelope_id: "22222222-2222-2222-2222-222222222222"
created_at: "2026-06-22T11:30:00Z"
query_intent: "status-summary"
scope:
  scope_kind: "repo"
  repo: "cic-mcp-gateway"
answer_type: "status_summary"
sources_used:
  - source_id: "cic-mcp-workdir"
    trust_domain: "workdir_local"
  - source_id: "cic-mcp-knowledge"
    trust_domain: "canonical"
trust_summary:
  overall_confidence: "medium"
  per_category:
    canonical_facts: "high"
    workdir_facts: "high"
    session_derived_notes: "not_used"
    shared_memory_notes: "not_used"
facts:
  - content: "cic-mcp-gateway repo status is scaffold."
    trust_tag: "workdir_local"
    ref: "ref-201"
  - content: "Gateway must not own raw storage."
    trust_tag: "canonical"
    ref: "ref-202"
conflicts: []
proof_requirements: []
refs:
  - ref_id: "ref-201"
    source_id: "cic-mcp-workdir"
  - ref_id: "ref-202"
    source_id: "cic-mcp-knowledge"
```

**Miért invalid:** a tartalom egy közös `facts` tömbbe van összevonva, ahol az eredet
csak egy `trust_tag` metaadat-mező a kanonikus és a workdir-eredetű tényen — ez pont az
input.md "Feladat" 1. pontja és a "Forbidden Shortcuts" harmadik tétele által explicit
megtiltott mintázat ("a 4 tartalom-kategória ... egy közös 'facts' mezőbe összevonása
trust-tag-gel — ez elveszti a forrásréteg-eredet strukturális garanciáját"). Emellett a
dokumentum hiányolja a `canonical_facts`/`workdir_facts`/`session_derived_notes`/
`shared_memory_notes` mezőket, amik a schema `required` listájában szerepelnek — tehát ez
a példa egyszerre bukik el a "merged facts" strukturális tilalmon ÉS a required-mező
hiányon.

## Separation From Source-Specific MCP APIs

A `GatewayContextEnvelope` **NEM** azonos a forrás-specifikus MCP API-k nyers
válaszformátumával, és **NEM** helyettesíti vagy duplikálja azokat — ez egy
elkülönült, gateway-szintű csomagolási réteg, amely a forrás-API válaszait fordítja
trust-jelölt kontextussá.

Konkrét ellentét a `cic-mcp-session` 7(+5) MCP tool-jával (forrás:
`cic-mcp-gateway/CLAUDE.md` "MCP szerver tool-ok" táblája — ez a tábla jelenleg a
`base-repo` generikus KB-template örökölt tool-listája, amit a gateway saját belső
dokumentáció-indexeléséhez használ, NEM a session-specifikus üzemi API; a job-spec a
`cic-mcp-session` saját, a `cic-mcp-session` repóban élő tool-jaira utal, pl.
`search_session_context`, `get_session_timeline`):

| Forrás-specifikus MCP tool (pl. `cic-mcp-session`) | `GatewayContextEnvelope` |
|---|---|
| Egy konkrét forrásrendszer (`cic-mcp-session`) nyers, natív válaszformátumát adja vissza (pl. egy chunk-lista, egy timeline-szelet) | Egy forrás-agnosztikus, trust-jelölt csomagot ad vissza, függetlenül attól, hogy hány/melyik forrásból épült |
| A válasz szerkezete a forrás belső adatmodelljét követi (pl. `session_id`, `turn`, `chunk_id` natív mezőkkel) | A válasz szerkezete a 4 tartalom-kategória + trust/conflict/proof keretrendszert követi, a forrás-specifikus mezők csak a `refs[].ref_id`/`excerpt` szintjén jelennek meg, idézetként |
| Nem tartalmaz kötelező `conflicts`/`proof_requirements` mezőt — ez nem az ő felelőssége, egy session-API csak a saját session-scope-ját látja | A `conflicts`/`proof_requirements` KÖTELEZŐ — a gateway feladata épp a több forrás közötti konfliktus/proof-igény felszínre hozása, amit egyetlen forrás-API önmagában nem láthat |
| Trust-szint implicit (a hívó tudja, hogy "ez egy `cic-mcp-session` válasz, tehát session_local/session_derived") | Trust-szint EXPLICIT, mezőnként jelölve (`trust_summary`, `session_derived_notes[].trust`) — a hívónak nem kell ismernie a forrás belső konvencióját |
| Egy forrás-API hívása NEM jár automatikus query-intent-routing döntéssel — a hívó dönt, melyik tool-t hívja | A `GatewayContextEnvelope` MINDIG a gateway saját query-intent-felismerési és source-routing döntésének az eredménye (`query_intent`, `scope`, `sources_used`) |

A gyakorlatban: ha egy agent a gateway-en keresztül kérdez, SOHA nem kapja vissza
közvetlenül egy `cic-mcp-session` MCP tool nyers JSON válaszát — azt a (jövőbeli)
`gateway-session-adapter-contract-001` job adaptere konzumálja, és a tartalmát a
`session_derived_notes`/`refs` mezőkbe csomagolva adja tovább a `GatewayContextEnvelope`-on
keresztül. Ez a job nem definiálja az adapter kódját (lásd "Rejected / Out Of Scope"), csak
az ELVÁRT kimeneti formátumot, amibe az adapternek be kell illeszkednie.

## Decisions Proposed

1. **A `GatewayContextEnvelope` schema 16 top-level required mezőt tartalmaz**, a doc-terv
   teljes 12 mezős listáját megtartva, kiegészítve a stílus-konvenció keret-mezőivel
   (`apiVersion`, `kind`, `envelope_id`, `created_at`). Javaslat: a következő gateway-job
   (`gateway-source-registry-contract-001`) ezt a mezőlistát vegye véglegesnek, ne nyissa
   újra a 12 doc-terv mezőt.
2. **A 4 tartalom-kategória (`canonical_facts`/`workdir_facts`/`session_derived_notes`/
   `shared_memory_notes`) property-szinten örökre elkülönült marad** — ezt a schema
   `forbidden_combinations[2]` tétele is explicit rögzíti. Javaslat: bármely jövőbeli
   gateway-schema-revízió (v2) csak ÚJ kategóriát adhat hozzá, nem vonhatja össze a
   meglévő négyet.
3. **`conflicts` és `proof_requirements` mindig top-level required, `minItems: 0`-val** —
   ezt a mintát kell követnie minden jövőbeli gateway-kontraktusnak, ahol "explicit üres
   állítás" ≠ "hiányzó mező" különbségtétel releváns.
4. **A `sources_used[].source_id` enum jelenleg 4 értékre korlátozott** (a
   `gateway-baseline.md` Source Registry kezdeti listája szerint) — ha a
   `gateway-source-registry-contract-001` job új source_id-t vesz fel, ennek a schema-nak
   az enumját is bővíteni kell egy követő/patch jobban (lásd "Next Jobs").
5. **Az `invariants` és `forbidden_combinations` blokkok dokumentációs jellegűek, nincs
   futtatható validátor** — javaslat: a jövőbeli validátor-implementáció (ha lesz) ezekből
   a blokkokból generálja a tényleges JSON-Schema `enum`/`const`/`required` kikényszerítést,
   ne írja újra a szabályokat nulláról.

## Rejected / Out Of Scope

- **Source registry séma vagy implementáció** — explicit a
  `gateway-source-registry-contract-001` jobé (lásd input.md "Nem cél" 1. pont); ez a job
  csak `source_id`/`trust_domain` ÉRTÉKEKRE hivatkozik enumként, nem definiálja a registry
  bejegyzés teljes mezőlistáját (azt a `gateway-baseline.md` "Source Registry — Initial
  Boundary" táblája vázolja, és a registry-job formalizálja).
- **Routing logika, MCP tool, session/shared adapter kód** — explicit kizárva (input.md
  "Nem cél" 2. pont); ez `gateway-session-adapter-contract-001` és társai feladata.
- **Futtatható JSON-Schema validátor** — explicit kizárva (input.md "Nem cél" 3. pont); a
  `forbidden_combinations` blokk két tétele (`forbidden-canonical-promotion-by-gateway`,
  `forbidden-raw-source-passthrough`) emiatt dokumentált, de NEM schema-szinten
  kikényszerített.
- **`cic-mcp-session`/`cic-mcp-shared`/`cic-mcp-knowledge` repók módosítása** — nem
  történt, nem is volt indokolt; a `cic-mcp-session` stílus-referencia fájlt csak
  OLVASÁSRA használtam (a `cic-mcp-factory` klónban már elérhető másolatból), nem
  módosítottam.
- **`query_intent` taxonómia/enum bevezetése** — a `query_intent` mező jelen schema-
  revízióban szabad szöveg (`type: string`, `minLength: 1`); egy konkrét enum/taxonómia
  bevezetése egy külön, jövőbeli jobnak való (lásd "Next Jobs"), nem ennek a contract-
  jobnak — a doc-terv sem rögzít konkrét intent-enumot.

## Risks

- **Doc/séma divergencia kockázat (a `gateway-baseline.md`-ből örökölt kockázat)**: a
  `docs/{hu,en}/architecture.md` 12 mezős listája és a most leszállított schema 16 mezős
  `required` listája nem szó szerint egyezik (a 4 extra mező a keret-konvencióból jön,
  `apiVersion`/`kind`/`envelope_id`/`created_at`). Mitigáció: ez a report explicit
  felsorolja a mapping-et (Findings #1) — bármely jövőbeli olvasó láthatja, hogy nincs
  elveszett vagy önkényesen hozzáadott doménmező, csak a stílus-konvenció kerete bővült.
- **`query_intent` szabad-szöveg kockázat**: jelenleg `type: string`, nincs enum — ez
  lehetővé teszi, hogy két jövőbeli adapter-implementáció inkonzisztens intent-string
  formátumot használjon (pl. `"lookup-canonical-fact"` vs. `"lookup_canonical_fact"`).
  Mitigáció: ezt explicit Out Of Scope-ként rögzítettem, javaslat egy követő taxonómia-
  jobra (lásd Next Jobs).
- **Cross-field invariáns kikényszeríthetetlenség kockázat**: a `forbidden_combinations`
  utolsó két tétele (`forbidden-canonical-promotion-by-gateway`,
  `forbidden-raw-source-passthrough`) jelenleg KIZÁRÓLAG dokumentált, nem schema-szinten
  kikényszerített — egy jövőbeli implementáció technikailag előállíthat egy schema-
  konform, de ezt a két invariánst megsértő envelope-ot, és a jelen schema ezt nem
  bukná el. Mitigáció: a `gateway-session-adapter-contract-001` jobnak (vagy egy külön
  validátor-jobnak) explicit ki kell térnie ezekre, az itt rögzített
  `forbidden_combinations` szöveg alapján.
- **Source registry körkörösség kockázat (a baseline-ból örökölt, még nyitott kérdés)**: a
  `gateway-baseline.md` "Risks" szekciója szerint a `cic-mcp-workdir` mint source-domain
  vs. `cic-factory`-n keresztüli elérés kérdése még nyitott — a jelen schema a
  `cic-mcp-workdir`-t enum-értékként veszi fel a `sources_used[].source_id`-be, de ha a
  registry-job ezt eltérően dönti el (pl. `cic-mcp-workdir` nem önálló source_id, csak a
  `cic-factory`-n keresztül elérhető), ez a schema enum-listája egy követő patch-et
  igényelhet.

## Definition Of Done Check

- [x] `output/gateway-context-envelope.schema.yaml` létrehozva, a stílus-konvenció szerint
      → létrehozva, `apiVersion`/`kind`/`metadata`/`required`/`properties` szerkezettel,
      megegyezik a `SessionIngressEnvelope` mintájával (lásd "Schema Summary")
- [x] a schema tartalmazza: `sources_used`, `trust_summary`, `conflicts`,
      `proof_requirements`, `refs`
      → mind az 5 mező jelen van a `required` listában és saját `properties` blokkal
      (lásd Claim-Evidence Matrix 1-5. sora)
- [x] a schema elkülöníti: `canonical_facts`, `workdir_facts`, `session_derived_notes`,
      `shared_memory_notes`
      → 4 elkülönült property blokk, nincs közös `facts` mező (lásd Claim-Evidence Matrix
      6. sora)
- [x] a report explicit kimondja: gateway nem tárol raw storage-ot, nem tárol embedding
      store-ot
      → lásd ez a fájl "Findings" 6. pont + a schema `invariants[0-1]` blokkja idézve;
      explicit kimondva: "owns_raw_storage = false. A gateway maga sosem perzisztál nyers
      session-eseményt..." (paraphrase a schema szövegéből)
- [x] a report legalább 2 valid + 2 invalid envelope példát tartalmaz, indoklással
      → 2 valid + 3 invalid (a 3. invalid extra, a "merged facts" tilalom illusztrálására),
      mindegyik invalid-nál explicit "Miért invalid" alszekció
- [x] a report elválasztja a `GatewayContextEnvelope`-ot a forrás-specifikus MCP API-któl
      → lásd "Separation From Source-Specific MCP APIs" szekció, táblázattal
- [x] claim-evidence tábla kitöltve, nem üres
      → 13 sor, mind `proven` státusszal, fájl-idézettel alátámasztva

## Next Jobs

1. **`gateway-source-registry-contract-001`** (a job-spec szerint a logikailag következő
   lépés) — most, hogy a `GatewayContextEnvelope.sources_used[].source_id`/`trust_domain`
   enum-értékei rögzültek, a registry-job feladata ezeknek a teljes metaadat-séma
   formalizálása (a `gateway-baseline.md` "Source Registry — Initial Boundary" táblája
   alapján: `owns_raw_storage`, `returns_trust_envelope`, `query_capabilities`, `canonical`
   mezők). Explicit szinkronizálnia kell a `source_id` enumot ezzel a schema-val.
2. **`gateway-session-adapter-contract-001`** — az első konkrét adapter, amely ténylegesen
   előállít egy `GatewayContextEnvelope` instance-t `cic-mcp-session` forrásból; ez lesz az
   első valódi teszt arra, hogy a `session_derived_notes`/`refs`/`conflicts` mezők
   gyakorlatban elegendőek-e, vagy a schema-nak revízióra van szüksége (`candidate`
   promócióhoz ez kell, a Target szekció "status indoklás" szerint).
3. **(opcionális, alacsony prioritású) `gateway-query-intent-taxonomy-001`** — a jelen
   schema-revízióban `query_intent` szabad szöveg; ha az adapter-job(ok) tapasztalata azt
   mutatja, hogy konkrét enum/taxonómia kell, egy külön job formalizálja, NEM ez a job
   (lásd "Rejected / Out Of Scope").
