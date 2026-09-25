# Baseball Sabermetrics MCP

A local Model Context Protocol server that lets an MCP client inspect and query baseball datasets in SQLite. It imports the SABR Lahman CSV release, Retrosheet event files and processed CSVs, the Chadwick Baseball Bureau Persons Register, Retrosplits CSV files, and other user-supplied CSV datasets.

The project contains no baseball data. Download and review each source release yourself, then import it into a local SQLite file. The MCP process opens that file read-only; ingestion is a separate CLI operation.

## Requirements

- Python 3.10 or newer
- No third-party Python runtime packages

## Install

From this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The commands are `baseball-sabermetrics` (ingestion) and `baseball-sabermetrics-mcp` (MCP stdio server).

## Import data

Pass a directory, a single CSV or event file, or the original ZIP archive. The default database is `data/baseball.sqlite3`; set `BASEBALL_MCP_DB` or use `--db` to choose another location.

```sh
baseball-sabermetrics ingest lahman /path/to/lahman-csv.zip --version 2025 --db data/baseball.sqlite3
baseball-sabermetrics ingest retrosheet /path/to/retrosheet-event-files.zip --version 2026-08 --db data/baseball.sqlite3
baseball-sabermetrics ingest csv chadwick_register /path/to/register/data --db data/baseball.sqlite3
baseball-sabermetrics ingest csv chadwick_retrosplits /path/to/retrosplits/csv --db data/baseball.sqlite3
baseball-sabermetrics ingest csv statcast_csv /path/to/statcast-export.csv \
  --version "2025 regular season, batter query" \
  --url "https://baseballsavant.mlb.com/statcast_search?your-query" \
  --db data/baseball.sqlite3
```

The Lahman and generic CSV importers stream every `.csv` under a directory or ZIP archive into source-prefixed tables; a single CSV file can also be imported. The Retrosheet event importer streams `.EV?` and `.ED?` files from a directory or ZIP archive, or imports one event file directly. It stores file-header records such as `version`, game ids, season, `info` records, common play fields, and each per-game source record line's original content. Its parsed play columns are inning, batting team, batter id, count, pitches, and the original event text. Retrosheet processed CSV files can be imported with `ingest csv retrosheet_csv /path/to/csv-directory-or-zip`.

When the Chadwick Register import includes `data/people-0.csv` through `people-f.csv`, the importer retains those original shard tables and also creates `chadwick_register_people`, a combined table indexed on available cross-reference keys. This makes it practical to join Retrosheet batter IDs to MLBAM, Baseball-Reference, or FanGraphs IDs and then compare them with Statcast exports.

Generic imports use the dataset id as a table prefix. For example, `chadwick_register/data/people-0.csv` becomes `chadwick_register_people_0`. CamelCase Lahman filenames are converted to snake_case after the prefix, for example `BattingPost.csv` becomes `lahman_batting_post`. CSV column headings are preserved, with empty cells stored as NULL and numeric cells stored as SQLite numbers when they can be safely parsed.

Reimporting a dataset id replaces the tables previously imported under that id. Different ids can coexist in one SQLite file. `--version`, `--url`, and `--license` are recorded in the MCP dataset catalog; use the exact release label or export query URL for reproducibility. For multiple exports from one source, use distinct dataset ids and provide their source details. For an unlisted public CSV dataset, use a distinct id such as `custom_2025` and record its provenance and terms:

```sh
baseball-sabermetrics ingest csv custom_2025 /path/to/csv \
  --name "Dataset name" \
  --url "https://source.example/data" \
  --license "Source license and attribution terms" \
  --db data/baseball.sqlite3
```

## MCP client configuration

Configure the client to start `baseball-sabermetrics-mcp` with `BASEBALL_MCP_DB` set to the imported SQLite file. For clients that accept JSON stdio server entries, the shape is:

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

The server speaks MCP over newline-delimited JSON-RPC on stdin/stdout. It supports protocol versions `2024-11-05`, `2025-03-26`, `2025-06-18`, and `2025-11-25`.

## MCP tools and resources

- `list_datasets`: supported sources, formats, provenance, reuse notes, and installed state.
- `list_tables`: available SQLite tables, optionally filtered by dataset id.
- `describe_table`: source table, columns, imported row count, and dataset id.
- `query_sql`: one read-only SQLite `SELECT` or `WITH` statement; maximum 500 rows, 20,000 SQL characters, a five-second SQLite execution budget, and a bounded response size.
- `baseball://datasets`, `baseball://tables`, and `baseball://schema`: JSON resources describing sources and the local database.

Writes, schema changes, `ATTACH`, and `PRAGMA` statements are denied. SQL runs against a SQLite read-only connection. Import files only from sources you trust; keep the MCP process pointed at a database you control.

Example query:

```sql
SELECT playerID, yearID, teamID, HR, RBI
FROM lahman_batting
WHERE yearID = 2025 AND HR >= 40
ORDER BY HR DESC
LIMIT 20
```

Use `list_tables` and `describe_table` first when release schemas differ.

Example cross-source player-ID join:

```sql
SELECT p.game_id, p.inning, p.batter_id, r.key_mlbam, r.key_bbref, r.key_fangraphs
FROM retrosheet_events_plays AS p
LEFT JOIN chadwick_register_people AS r ON r.key_retro = p.batter_id
LIMIT 25
```

## Supported source catalog and reuse

- **SABR Lahman Database:** [official source and release downloads](https://sabr.org/lahman-database/). The release changes over time and currently includes statistics licensed from Seamheads for Negro Leagues. This project does not bundle Lahman files; retain the exact release notices and license included with the data.
- **Retrosheet:** [event and processed CSV downloads](https://www.retrosheet.org/downloads/). Retrosheet permits reuse with an attribution requirement. When transferring Retrosheet data or a product based on it, prominently include: “The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at 20 Sunset Rd., Newark, DE 19711.” Retrosheet also disclaims guarantees of accuracy.
- **Chadwick Persons Register:** [public repository and README](https://github.com/chadwickbureau/register). Its public README identifies the data under the Open Data Commons Attribution License (ODC-BY) 1.0. It is an evolving public extract; consult the source for the version's detailed terms.
- **Chadwick Retrosplits:** [public repository and README](https://github.com/chadwickbureau/retrosplits/blob/master/README.md). The README identifies ODbL for the database and DBCL for individual contents; it also says the underlying data is copyrighted by Retrosheet, so preserve both applicable attribution notices.
- **MLB Statcast Search:** [Baseball Savant search](https://baseballsavant.mlb.com/statcast_search) supports CSV export for pitch-, game-, player-, team-, and season-level queries; see its [CSV field documentation](https://baseballsavant.mlb.com/csv-docs). Imports retain the exported columns, but not the source query URL or filters unless the operator records them with `--url` and `--version`. For pitch velocity, the documentation notes that 2008–2016 values come from Pitch F/X and are adjusted to the later scale.

The source catalog is convenience metadata, not a substitute for the actual files' notices. This server does not download or redistribute data. Confirm the exact terms for each release before sharing imported databases or query results.

## Development

The runtime uses only the Python standard library. The MCP stdio handler is implemented directly over JSON-RPC so this project does not need to fetch third-party packages to run.
