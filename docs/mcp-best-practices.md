# MCP best-practices audit

This implementation audit uses the [MCP Best Practices: Architecture & Implementation Guide](https://modelcontextprotocol.info/docs/best-practices/) requested for this project. Protocol-specific details are cross-checked against the [official MCP Tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [Resources specification](https://modelcontextprotocol.io/specification/2026-07-28/server/resources), [Versioning and Compatibility](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning), and [stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio).

The guide is advice, not a substitute for the protocol specification. Annotations remain client hints. The server's local transport boundary and SQLite controls provide the actual protections described below.

| Practice | Implementation in this server |
| --- | --- |
| Keep tools focused and easy to choose | Four separate tools list sources, list tables, describe one table, or run one read-only SQL statement. Descriptions explain what each tool returns. |
| Declare the contract precisely | Each tool has an input schema with required fields, types, numeric/string limits, and no unknown fields; each also publishes an output schema. [`mcp-interface.json`](mcp-interface.json) is generated from these runtime definitions. |
| Use honest behavior hints | Every tool declares `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, and `openWorldHint: false`. Calls only inspect a local database. The importer is a separate CLI. |
| Return structured results | Successful tools include both `structuredContent` and a JSON text block for display and compatibility. Tool failures set `isError: true`. |
| Validate inputs at the boundary | Runtime validation repeats schema type, required-field, allowed-property, string-length, and numeric-bound checks. SQLite has its own query-length, row, execution-time, and authorizer controls. |
| Bound protocol input and diagnostics | The stdio reader processes request lines in bounded chunks and rejects a line over 1,000,000 bytes. Unexpected error logs include exception classes rather than exception text that could contain SQL or local paths. |
| Fail safely and report useful errors | Recoverable argument/query failures become tool results; missing resources use `-32002` only in legacy mode and `-32602` in modern mode; unexpected database details go to stderr, while clients receive a generic error. Stdout is kept for protocol messages. |
| Bound work and large responses | Queries are single statements limited to 20,000 characters, five seconds, 500 rows, and 180,000 serialized data bytes. Table listings are paginated. The schema resource includes only its first page; per-table details are available with `describe_table`. |
| Provide useful health and deployment behavior | `ping` is implemented. The supported deployment is local stdio; no unauthenticated HTTP listener is created. Resources are static snapshots because imports occur outside the MCP process. |
| Respect current and legacy MCP versions | Modern `2026-07-28` requests use per-request protocol and capability metadata; legacy `2025-11-25` and `2025-06-18` requests use the initialization handshake. `server/discover` advertises all supported versions. |
| Apply defense in depth | The server uses a `mode=ro` SQLite URI, `query_only`, a deny-by-default list of write/schema operations, selected filesystem-function denials, and OS-managed file permissions. Tool hints are not treated as enforcement. |
| Limit request volume | Tool invocations are capped at 120 per minute per server process. Query-level time, row, SQL length, and result-size bounds apply separately. |
| Handle untrusted content | Tool descriptions, initialization instructions, and security docs state that source values are untrusted data and not instructions. The server does not execute source text as code. |
| Document data rights and provenance | Dataset entries include source URLs and reuse notes. OBP's data license is explicitly separated from the code license, including its additional exclusion. No upstream files are bundled. |

## Verification coverage

The verification scripts are intentionally offline and use temporary fixtures. They cover MCP initialization and discovery, data ingestion, read-only query behavior, schema/result consistency, the OpenBiomechanics catalog and CSV importer, documentation, and repository metadata. The GitHub Actions CI workflow (`.github/workflows/quality.yml`) runs on push, pull request, and manual `workflow_dispatch`, checking Python 3.10 through 3.14.

## Remaining deployment limits

- The MCP stdio server is designed for one local operator and a local SQLite file. It is not a hosted service or multi-tenant access-control layer.
- The server limits each query, but it does not provide per-user authorization within one database. A client granted access can query all tables in that file.
- The import command is trusted local code with write access to the chosen database. Review files and source terms before running it.
- The project records provenance supplied by the operator; it cannot independently prove a dataset version or legal right to use a file.
