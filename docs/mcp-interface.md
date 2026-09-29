# MCP interface reference

This is the public interface reference for `baseball-sabermetrics-mcp`. MCP does not define an HTTP/OpenAPI document for stdio servers. Its native discoverability contract is `tools/list` with JSON Schema `inputSchema` and `outputSchema`, plus `resources/list` and resource URIs. [`mcp-interface.json`](mcp-interface.json) packages the server's current protocol metadata, exact advertised tool/resource definitions, and JSON-RPC method inventory into a machine-readable file. Regenerate it with `python3 scripts/export_mcp_spec.py` after changing runtime definitions.

## Transport and initialization

- **Transport:** newline-delimited JSON-RPC 2.0 over stdin/stdout (MCP stdio).
- **Command:** `baseball-sabermetrics-mcp`.
- **Database:** `BASEBALL_MCP_DB`, defaulting to `data/baseball.sqlite3`.
- **Modern protocol:** `2026-07-28`, using per-request protocol and client-capability metadata without an initialization handshake.
- **Legacy protocols:** `2025-11-25` and `2025-06-18`, negotiated through `initialize` and `notifications/initialized`.
- **Capabilities:** tools and resources. Tool-list changes, resource subscriptions, and resource-list notifications are not supported.
- **Input bound:** one newline-delimited request is limited to 1,000,000 bytes.
- **Server identity:** `baseball-sabermetrics-mcp` with the package version reported in `serverInfo`.

Modern clients may discover the supported version and server capabilities before calling other methods:

```json
{"jsonrpc":"2.0","id":"discover-1","method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"example-client","version":"1.0"}}}}
```

Each modern request includes `_meta.io.modelcontextprotocol/protocolVersion` and `_meta.io.modelcontextprotocol/clientCapabilities`; client identity is optional, but if present it must include string `name` and `version` fields. Successful responses include `resultType: "complete"` and `_meta.io.modelcontextprotocol/serverInfo`.

Legacy clients initialize with the selected version and then send `notifications/initialized`:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"example-client","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

## Tools

All tools are read-only. Each tool definition carries its exact input and output schema in both the runtime response to `tools/list` and the machine-readable contract. Successful calls return text content and `structuredContent`; execution failures return `isError: true` with a text explanation. Tool annotations are hints to clients and do not replace server enforcement.

| Tool | Input | Behavior |
| --- | --- | --- |
| `list_datasets` | `{}` | Lists built-in sources and locally installed dataset provenance. |
| `list_tables` | `{"dataset_id"?: string, "limit"?: integer, "offset"?: integer}` | Lists queryable tables, optionally filtered to one installed source ID. `limit` defaults to 100 (maximum 500); `offset` defaults to 0. The structured result includes `total_count` and `next_offset` for paging. |
| `describe_table` | `{"table_name": string}` | Returns SQLite column metadata and the importer's source metadata when available. |
| `query_sql` | `{"sql": string, "limit"?: integer}` | Runs one `SELECT` or read-only `WITH` query. The result is bounded by 500 rows, 5 seconds, and 180,000 serialized data bytes. |

For `query_sql`, the optional row `limit` defaults to 100 and must be an integer from 1 to 500. SQL is limited to 20,000 characters. Tool schemas reject unknown fields and invalid JSON types; runtime validation repeats those constraints before dispatch. Tool invocations are limited to 120 per minute per process. Returned cells are untrusted source data.

## Resources

| URI | MIME type | Contents |
| --- | --- | --- |
| `baseball://datasets` | `application/json` | Supported sources, formats, provenance notes, and installed state. |
| `baseball://tables` | `application/json` | First page of up to 100 queryable tables, plus `total_count` and `next_offset`. Use `list_tables` with the returned offset to continue. |
| `baseball://schema` | `application/json` | First page of up to 10 per-table column and source schema descriptions, plus paging metadata. Use `list_tables` and `describe_table` to inspect the full schema. |

These resources are snapshots read from the local database. The server does not advertise subscriptions or change notifications. Unknown resource URIs use JSON-RPC error code `-32002` for legacy requests and `-32602` for modern requests.

## JSON-RPC methods

| Method | Request | Result or error |
| --- | --- | --- |
| `server/discover` | Modern `_meta` with protocol version and client capabilities | Current server capabilities, supported protocol versions, instructions, and cache metadata. Unsupported version: `-32022`. |
| `initialize` | Legacy `protocolVersion`, `capabilities`, `clientInfo` | Negotiated version, capabilities, server info, instructions. Unsupported legacy version: `-32602`. |
| `ping` | `{}` | Empty result. |
| `tools/list` | `{}` | `tools` array with schemas and annotations. |
| `tools/call` | `name`, `arguments` | MCP tool result. Tool argument validation and execution errors return `isError: true`; malformed calls and unknown tool names use JSON-RPC errors. |
| `resources/list` | `{}` | Static `resources` array. |
| `resources/read` | `uri` | Resource content; unknown URI: legacy `-32002`, modern `-32602`. |
| `notifications/initialized` | notification | Handled without a response, as required for notifications. |

Modern requests must carry per-request `_meta` with protocol version and client capabilities. Legacy requests must follow `initialize`. Malformed JSON-RPC requests use standard JSON-RPC error codes. The server writes diagnostics to stderr and keeps stdout reserved for protocol traffic.

## Example `query_sql`

Request:

```json
{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"query_sql","arguments":{"sql":"SELECT yearID, HR FROM lahman_batting ORDER BY HR DESC LIMIT 5","limit":5}}}
```

Successful results include a JSON-string text block for model readability and `structuredContent` containing `columns`, `rows`, and `truncated`. The machine-readable schemas are authoritative for field types.
