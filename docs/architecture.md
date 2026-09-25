# Architecture

## Runtime boundary

```text
source files supplied by operator
            |
            v
baseball-sabermetrics CLI ---- writes ----> local SQLite database
                                                ^
                                                | read-only URI + SQLite authorizer
                                                |
MCP client <---- JSON-RPC over stdio ---- baseball-sabermetrics-mcp
```

Ingestion and serving are separate processes and commands. The CLI creates tables and a small provenance catalog. The MCP server does not fetch sources and does not expose an HTTP listener. It opens the configured SQLite file with `mode=ro`, enables `query_only`, and installs a SQLite authorizer for user SQL.

## Package modules

- `baseball_mcp.catalog` contains source IDs, formats, upstream links, and reuse notes.
- `baseball_mcp.ingest` reads CSV, ZIP, and Retrosheet event inputs; creates source-prefixed tables; and records import metadata.
- `baseball_mcp.server` implements MCP initialization, tool/resource discovery, bounded SQL execution, and the stdio JSON-RPC loop.
- `baseball_mcp.cli` exposes imports as `baseball-sabermetrics`.
- `scripts/export_mcp_spec.py` renders the checked-in machine-readable interface document from the runtime tool and resource definitions.

## Data model

Imported source tables use a lowercase dataset-ID prefix. For example, Lahman `BattingPost.csv` maps to `lahman_batting_post`; a CSV named `poi_metrics.csv` under the OpenBiomechanics pitching import maps to `openbiomechanics_pitching_poi_metrics`. The `_baseball_mcp_datasets` and `_baseball_mcp_tables` tables retain dataset provenance, source filenames, source-column names, and imported row counts. They are not shown as user data tables.

Retrosheet event ingestion creates `retrosheet_events_games`, `retrosheet_events_records`, `retrosheet_events_file_headers`, and `retrosheet_events_plays`. The parsed play fields are a convenience view of the source line; `raw_record` preserves the original record text. Chadwick Register imports retain their original shard tables and optionally add the indexed `chadwick_register_people` crosswalk.

## MCP surface

The server advertises the same tool definitions through MCP `tools/list` and the checked-in interface document. Tools return both text content for model display and `structuredContent` for clients that consume JSON. Each tool publishes an input and output JSON Schema and read-only/local behavior annotations. The annotations are hints; the SQLite URI mode and authorizer enforce the query restriction.

Three JSON resources expose dataset, table, and schema catalogs. Table and schema snapshots are paged to keep resource responses bounded; use `list_tables` with an offset and then `describe_table` to inspect additional tables. Since source data is local and imports happen outside the MCP process, the server does not advertise resource subscriptions or list-change notifications.

See the [MCP interface reference](mcp-interface.md) for the public request/result contract and current limits.
