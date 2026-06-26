# cic-mcp-gateway

Trust-domain aware context compiler és agent-facing frontend a CIC agent-kontextus
(`cic-mcp-*` család) számára.

A `cic-mcp-*` család trust-domain rétegezésében ez a komponens nem tárol semmit, hanem a
session/workdir/knowledge/shared forrásokat fordítja egységes, trust-jelölt kontextus-csomaggá.

## Mi ez és mi nem

**Igen:**
- query intent felismerés
- trust-domain source routing
- source registry használat
- conflict/proof felszínre hozása
- `GatewayContextEnvelope` összeállítása
- agent-facing context API

**Nem:**
- raw event store
- embedding store
- factory runner
- canonical promotion
- generic proxy (`route_query` ≠ `search_all`)

A komponensek közti pontos határt lásd: [CLAUDE.md](CLAUDE.md).

## Státusz

`experimental` — a repo a `cic-mcp-factory` job-lifecycle-én keresztül épül fel, kapacitás-jobonként.

**Implementált (`implemented`):**
- `gateway_core/compile_context.py` — `compile_context()`: valódi session-source context compiler,
  subprocess-alapú MCP klienssel hívja a `cic-mcp-session` szervert, `GatewayContextEnvelope`-kompatibilis
  kimenetet állít elő
- `gateway_core/validate_envelope.py` — envelope schema validáció
- `mcp-server/gateway_server.py` — `get_gateway_context_pack` MCP tool (`session_id`, `session_repo_root`,
  `max_chunks`)
- Signed contracts: source registry schema, session adapter contract, context envelope schema (`output/`)

**Scaffold (kód van, de nincs bekötve):**
- knowledge / shared / workdir forrás-bekötés — `compile_context.py` explicit scope-on kívül hagyja,
  a mezők `[]` / `"not_used"` értékkel schema-validak de tartalommal üresek
- multi-source query intent routing — stub mezők az envelope-ban
- `source/` üres (a base-repo KB szerver ez alapján épít — gateway kontextusban nem használt)

## Kapcsolódó dokumentáció

- [`cic-mcp-factory` factory-docs](https://github.com/CentralInfraCore/cic-mcp-factory) — a komponens
  tervezési alapja (`architecture.md`, `acceptance-contract.md`, `execution-phases.md` Phase 1B/2)
- [`cic-mcp-session`](https://github.com/CentralInfraCore/cic-mcp-session),
  [`cic-mcp-shared`](https://github.com/CentralInfraCore/cic-mcp-shared),
  [`cic-mcp-knowledge`](https://github.com/CentralInfraCore/cic-mcp-knowledge) — azok a
  trust-domain forrásréteg, amiket ez a komponens route-ol, sosem maga tárol
