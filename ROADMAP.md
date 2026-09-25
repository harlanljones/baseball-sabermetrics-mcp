# Roadmap

This roadmap describes proposed work for Baseball Sabermetrics MCP. None of the items below should be read as implemented until its code, documentation, and review checks land in a pull request. The order reflects dependencies and user value; it has no delivery dates.

## Principles

- Keep the default server local, read-only, and lightweight.
- Preserve source identity, release details, and reuse notices. Never bundle upstream data with the software.
- Make ambiguity and missing data visible instead of guessing.
- Add optional dependencies only for capabilities that need them.
- Treat remote access as a separate security-sensitive deployment feature.

## Proposed sequence

| Stage | Proposal | Outcome |
| --- | --- | --- |
| 1. Reliable imports | Import manifests, checksums, quality reports, and safer archive handling; add cross-platform smoke coverage and verified client setup examples. | Operators can reproduce and inspect an import, and documented platform claims match tested environments. |
| 2. Baseball-aware discovery | Player/team lookup and season-stat tools built on imported tables and the Chadwick ID crosswalk. | MCP clients can find records without composing joins or guessing table names. |
| 3. Metric semantics | A metric reference resource followed by a small set of versioned calculations with explicit inputs and constants. | Clients can explain which formula and season assumptions produced a value. |
| 4. Larger files | Optional local Parquet ingestion, subject to benchmarks and an optional dependency. | Large CSV workflows have a documented alternative without increasing the default install footprint. |
| 5. Remote access, if needed | A separately reviewed Streamable HTTP transport with authentication and deployment guidance. | Remote use is opt-in, protected, and does not weaken local stdio defaults. |

Detailed requirements and acceptance criteria are in [the roadmap specifications](docs/roadmap-specs.md).

## Review gates for roadmap items

Each proposal should receive its own implementation review. Before it is called complete, update the interface contract and user docs where applicable, add focused regression coverage, verify source-rights and privacy implications, and record compatibility changes. Remote transport additionally requires a threat review and explicit deployment security guidance.
