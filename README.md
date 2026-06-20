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
Jelenleg a `base-repo` `mcp/main` template-jéből bootstrapelt MCP-szerver scaffold van benne,
saját gateway-specifikus implementáció (`GatewayContextEnvelope`, source registry) még nincs.

## Kapcsolódó dokumentáció

- [`cic-mcp-factory` factory-docs](https://github.com/CentralInfraCore/cic-mcp-factory) — a komponens
  tervezési alapja (`architecture.md`, `acceptance-contract.md`, `execution-phases.md` Phase 1B/2)
- [`cic-mcp-session`](https://github.com/CentralInfraCore/cic-mcp-session),
  [`cic-mcp-shared`](https://github.com/CentralInfraCore/cic-mcp-shared),
  [`cic-mcp-knowledge`](https://github.com/CentralInfraCore/cic-mcp-knowledge) — azok a
  trust-domain forrásréteg, amiket ez a komponens route-ol, sosem maga tárol
