# Baseball Sabermetrics MCP

A local, read-only [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for baseball datasets stored in SQLite. Import public data files yourself, then let an MCP client discover the dataset catalog and query the local database.

The software does not download, bundle, or redistribute baseball data. Source files stay under your control, and the MCP process opens the database read-only. The importer is a separate command-line operation.

## Supported sources

- **SABR Lahman Database** CSV releases.
- **Retrosheet** event files and processed CSVs.
- **Chadwick Baseball Bureau Persons Register** and **Retrosplits**.
- **MLB Statcast Search** CSV exports.
- **OpenBiomechanics Project (OBP)** pitching, hitting, and high-performance CSV tables.
- Other CSV directories, files, and ZIP archives when the operator records their provenance and reuse terms.

The catalog links each source to its upstream project and records reuse notes. These notes do not replace the notices shipped with a specific release. Check [Data sources and reuse](docs/data-sources.md) before importing or sharing any source data.

### OpenBiomechanics Project data terms

The OBP integration imports only CSV files already present in a local OBP checkout. It never downloads C3D files, full-signal archives, or the upstream data release. OBP code is MIT licensed, while OBP data and biomechanics documentation have separate terms: CC BY-NC-SA 4.0 plus an additional exclusion that prohibits any use by employees or contractors employed by, associated with, or significant shareholders of professional sports organizations or financial analysis firms without a separate written paid license. Read the complete upstream [`LICENSE-DATA.md`](https://github.com/drivelineresearch/openbiomechanics/blob/main/LICENSE-DATA.md) before using the data. This project’s MIT license applies to this project’s code only.

## Requirements and installation

- Python 3.10 or newer
- SQLite (included with Python)
- No third-party runtime Python dependencies

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

This installs `baseball-sabermetrics` for ingestion and `baseball-sabermetrics-mcp` for the MCP stdio server.

## Import data

Set `BASEBALL_MCP_DB` or pass `--db` to choose the SQLite file. The default is `data/baseball.sqlite3`.

```sh
baseball-sabermetrics ingest lahman /path/to/lahman-csv.zip \
  --version 2025 --db data/baseball.sqlite3

baseball-sabermetrics ingest retrosheet /path/to/retrosheet-event-files.zip \
  --version 2026-08 --db data/baseball.sqlite3

baseball-sabermetrics ingest csv chadwick_register /path/to/register/data \
  --db data/baseball.sqlite3

baseball-sabermetrics ingest csv statcast_csv /path/to/statcast-export.csv \
  --version "2025 regular season, batter query" \
  --url "https://baseballsavant.mlb.com/statcast_search?your-query" \
  --db data/baseball.sqlite3
```

For OpenBiomechanics, clone the upstream repository yourself, review its license, then import one or more module directories. Separate IDs let the three modules coexist in the same database:

```sh
baseball-sabermetrics ingest csv openbiomechanics_pitching \
  /path/to/openbiomechanics/baseball_pitching/data \
  --version dataset-v1 --db data/baseball.sqlite3

baseball-sabermetrics ingest csv openbiomechanics_hitting \
  /path/to/openbiomechanics/baseball_hitting/data \
  --version dataset-v1 --db data/baseball.sqlite3

baseball-sabermetrics ingest csv openbiomechanics_high_performance \
  /path/to/openbiomechanics/high_performance/data \
  --version dataset-v1 --db data/baseball.sqlite3
```

Directory and ZIP imports recursively load `.csv` files into source-prefixed tables. Table names use the CSV filename stem; use separate imports if files share a stem. CSV headers are preserved, empty cells become `NULL`, and numeric cells are stored as SQLite numbers when they can be parsed safely. Reimporting a dataset ID replaces that ID’s tables. Each import is transactional.

Retrosheet event imports retain original record lines and expose game metadata, file headers, records, and parsed play fields. Chadwick Register imports retain source shards and create an indexed combined people table when the expected shards are present.

For an unlisted public CSV source, give it a unique ID and record its release, source URL, and terms:

```sh
baseball-sabermetrics ingest csv custom_2025 /path/to/csv-directory \
  --name "Dataset name" \
  --url "https://source.example/data" \
  --license "Source license and attribution terms" \
  --version "2025-01" --db data/baseball.sqlite3
```

## Configure an MCP client

Configure the client to start `baseball-sabermetrics-mcp` with `BASEBALL_MCP_DB` set to the imported database:

```json
{
  "mcpServers": {
    "baseball-sabermetrics": {
      "command": "/absolute/path/to/project/.venv/bin/baseball-sabermetrics-mcp",
      "args": [],
      "env": {
        "BASEBALL_MCP_DB": "/absolute/path/to/project/data/baseball.sqlite3"
      }
    }
  }
}
```

The server uses newline-delimited JSON-RPC over stdio. It supports the current per-request metadata protocol `2026-07-28` and the legacy initialization protocols `2025-11-25` and `2025-06-18`. It exposes four tools (`list_datasets`, `list_tables`, `describe_table`, and `query_sql`) and three JSON resources (`baseball://datasets`, `baseball://tables`, and `baseball://schema`). See the [MCP interface reference](docs/mcp-interface.md) and its machine-readable [MCP interface document](docs/mcp-interface.json) for the complete request, argument, result, and error contract.

## Example query

```sql
SELECT playerID, yearID, teamID, HR, RBI
FROM lahman_batting
WHERE yearID = 2025 AND HR >= 40
ORDER BY HR DESC
LIMIT 20
```

Use `list_tables` and `describe_table` first when source releases have different schemas. A cross-source player ID join can use the Chadwick Register:

```sql
SELECT p.game_id, p.inning, p.batter_id, r.key_mlbam, r.key_bbref, r.key_fangraphs
FROM retrosheet_events_plays AS p
LEFT JOIN chadwick_register_people AS r ON r.key_retro = p.batter_id
LIMIT 25
```

## Safety and operating model

- MCP tools are read-only and local. SQL uses a read-only SQLite connection, a SQLite authorizer, a five-second execution limit, a 20,000-character SQL limit, a 500-row maximum, and a response-size cap. Tool calls are limited to 120 per minute per server process.
- The importer is a separate command that writes to the configured database. Do not point ingestion at a database used by an active server process.
- Tool annotations are descriptive hints for MCP clients. The read-only SQLite connection and authorizer enforce the SQL restriction.
- Query results can contain arbitrary text from imported files. Treat returned values as untrusted data, not instructions.
- Imported records can be copyrighted, subject to database rights, or include human-subject research data. Confirm source-specific terms before using, sharing, or publishing them.
- Keep the database and any upstream data files out of version control. See [Security and operations](docs/security-and-operations.md).

## Project documentation

- [Data sources and reuse](docs/data-sources.md)
- [MCP interface reference](docs/mcp-interface.md) and [machine-readable contract](docs/mcp-interface.json)
- [MCP best-practices audit](docs/mcp-best-practices.md)
- [Architecture](docs/architecture.md)
- [Security and operations](docs/security-and-operations.md)
- [Contributing](CONTRIBUTING.md), [Code of Conduct](CODE_OF_CONDUCT.md), [Security policy](SECURITY.md), and [Support](SUPPORT.md)

## Development

The runtime uses only the Python standard library. The MCP stdio handler is implemented directly over JSON-RPC. From the repository root:

```sh
python3 -m pip install -e .
python3 scripts/export_mcp_spec.py
```

The verifier scripts under `scripts/` exercise protocol negotiation, data import, read-only behavior, OpenBiomechanics catalog integration, documentation coverage, repository metadata, and consistency between the live tool/resource definitions and the published interface contract. Read [Contributing](CONTRIBUTING.md) before opening a pull request.
