# Security and operations

## Intended deployment

Run this server as a local MCP stdio subprocess. It does not implement HTTP or remote authentication, so do not expose its stdio process through a network bridge without adding and reviewing an appropriate authentication and authorization layer.

The process reads one SQLite database path from `BASEBALL_MCP_DB` (or `data/baseball.sqlite3`). The MCP server opens that file read-only and applies `PRAGMA query_only`, a SQLite authorizer, a query execution deadline, an SQL length limit, a row limit, and a serialized-result limit. The importer is a separate writer command. Treat the database, source files, and output as sensitive according to the data source's terms and your environment.

## Trust boundaries

- **Source files:** Import only files from sources you trust. A CSV can contain misleading text, malformed values, or content that attempts to influence an assistant. Query outputs are source data and should never be treated as system or developer instructions.
- **Local database:** Keep the database outside version control and restrict filesystem access. Do not use the server with a database that contains records the MCP client is not authorized to see.
- **SQL:** The server only accepts a single query statement and denies writes, schema changes, transactions, attachment/detachment, PRAGMA statements, and selected filesystem/extension functions. This is a defense-in-depth boundary, not a substitute for OS-level permissions or careful client configuration.
- **MCP client:** Tool annotations indicate read-only and closed-world behavior. MCP annotations are client hints, not authorization controls. The database open mode and SQLite authorizer enforce the read-only SQL boundary.
- **Data rights:** The MCP code license does not license data. Check source-specific terms before querying for a new purpose, exporting results, or sharing an imported database.

## Resource limits

- One newline-delimited MCP request, at most 1,000,000 bytes.
- One SQL statement, at most 20,000 characters.
- At most 500 result rows.
- Five seconds of SQLite execution per query.
- At most 180,000 bytes for the serialized query data; row truncation is reported with `truncated: true`.
- The server uses stderr for diagnostics and stdout only for JSON-RPC protocol messages.

## Operations

1. Import only approved local source files and retain the source release and license information.
2. Configure the MCP client to point to the resulting database path.
3. Discover datasets and tables before issuing queries; inspect evolving source schemas with `describe_table`.
4. Review what the client sends to the local server and keep the database path and source files out of logs and repository commits.
5. Upgrade from a reviewed source release. Reimport with the same ID only when replacement is intended; imports are transactional.

## Reporting a vulnerability

See [SECURITY.md](../SECURITY.md) for private reporting guidance. Include the affected version, a short impact description, and a reproducible report. Do not attach third-party source datasets or human-subject data to the report.
