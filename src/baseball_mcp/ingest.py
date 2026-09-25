"""Import user-supplied Lahman, Retrosheet, and public CSV files into SQLite."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import re
import sqlite3
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, TextIO

from .catalog import DATASET_BY_ID

EVENT_FILE = re.compile(r"\.(?:EV|ED)[A-Z]$", re.IGNORECASE)
INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
FLOAT = re.compile(r"^-?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)$|^-?(?:[0-9]+\.[0-9]*|\.[0-9]+)$")


def default_database_path() -> Path:
    import os

    return Path(os.environ.get("BASEBALL_MCP_DB", "data/baseball.sqlite3")).expanduser()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def open_database(path: str | Path) -> sqlite3.Connection:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, isolation_level=None, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    initialize_schema(connection)
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS _baseball_mcp_datasets (
            dataset_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            source_url TEXT,
            license TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            source_version TEXT
        );
        CREATE TABLE IF NOT EXISTS _baseball_mcp_tables (
            table_name TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            source_table TEXT NOT NULL,
            columns_json TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES _baseball_mcp_datasets(dataset_id) ON DELETE CASCADE
        );
        """
    )


def _source_info(
    dataset_id: str,
    display_name: str | None,
    source_url: str | None,
    license_text: str | None,
) -> tuple[str, str | None, str]:
    known = DATASET_BY_ID.get(dataset_id)
    if known:
        return (
            display_name or str(known["name"]),
            source_url if source_url is not None else known["url"],
            license_text or str(known["license"]),
        )
    return (
        display_name or dataset_id,
        source_url,
        license_text or "User supplied; verify and retain the source's terms.",
    )


def _table_prefix(dataset_id: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", dataset_id):
        raise ValueError("Dataset id must start with a lowercase letter and use only lowercase letters, numbers, hyphens, or underscores")
    prefix = re.sub(r"[^a-zA-Z0-9]+", "_", dataset_id).strip("_").lower()
    if not prefix or not prefix[0].isalpha():
        raise ValueError("Dataset id must begin with a letter and contain only letters, numbers, hyphens, or underscores")
    return prefix


def _slug(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "table"


def _safe_columns(headers: list[str]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    used: set[str] = set()
    for index, original in enumerate(headers, start=1):
        name = original.strip().lstrip("\ufeff") or f"column_{index}"
        candidate = name
        suffix = 2
        while candidate.casefold() in used:
            candidate = f"{name}__{suffix}"
            suffix += 1
        used.add(candidate.casefold())
        result.append((candidate, name))
    if not result:
        raise ValueError("CSV has no header columns")
    return result


def _typed_cell(value: str) -> Any:
    if value == "":
        return None
    if INTEGER.fullmatch(value):
        try:
            number = int(value)
            if -(2**63) <= number < 2**63:
                return number
        except ValueError:
            pass
        return value
    if FLOAT.fullmatch(value):
        try:
            number = float(value)
            if math.isfinite(number):
                return number
        except ValueError:
            pass
    return value


def _register_dataset(
    connection: sqlite3.Connection,
    dataset_id: str,
    display_name: str | None,
    source_url: str | None,
    license_text: str | None,
    source_version: str | None,
) -> None:
    name, url, license_value = _source_info(dataset_id, display_name, source_url, license_text)
    connection.execute(
        "INSERT INTO _baseball_mcp_datasets(dataset_id, display_name, source_url, license, imported_at, source_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (dataset_id, name, url, license_value, dt.datetime.now(dt.timezone.utc).isoformat(), source_version),
    )


def _replace_dataset(connection: sqlite3.Connection, dataset_id: str) -> None:
    for row in connection.execute(
        "SELECT table_name FROM _baseball_mcp_tables WHERE dataset_id = ?", (dataset_id,)
    ):
        connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(row['table_name'])}")
    connection.execute("DELETE FROM _baseball_mcp_tables WHERE dataset_id = ?", (dataset_id,))
    connection.execute("DELETE FROM _baseball_mcp_datasets WHERE dataset_id = ?", (dataset_id,))


def _table_metadata(
    connection: sqlite3.Connection,
    table_name: str,
    dataset_id: str,
    source_table: str,
    columns: list[tuple[str, str]],
    row_count: int,
) -> None:
    connection.execute(
        "INSERT INTO _baseball_mcp_tables(table_name, dataset_id, source_table, columns_json, row_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            table_name,
            dataset_id,
            source_table,
            json.dumps([{"name": name, "source_name": original} for name, original in columns], ensure_ascii=False),
            row_count,
        ),
    )


def _consolidate_chadwick_people(connection: sqlite3.Connection) -> dict[str, Any] | None:
    shards = connection.execute(
        "SELECT table_name, source_table, columns_json, row_count "
        "FROM _baseball_mcp_tables WHERE dataset_id = 'chadwick_register' ORDER BY source_table"
    ).fetchall()
    people_shards = [
        row for row in shards
        if re.search(r"(?:^|/)people[-_]([0-9a-f])$", row["source_table"], re.IGNORECASE)
    ]
    if not people_shards:
        return None

    source_columns = json.loads(people_shards[0]["columns_json"])
    columns = [(item["name"], item["source_name"]) for item in source_columns]
    source_names = [item["source_name"] for item in source_columns]
    for row in people_shards[1:]:
        shard_columns = json.loads(row["columns_json"])
        if [item["source_name"] for item in shard_columns] != source_names:
            raise ValueError(f"Chadwick Register people shard has a different schema: {row['source_table']}")

    merged_table = "chadwick_register_people"
    column_list = ", ".join(quote_identifier(name) for name, _ in columns)
    connection.execute(f"CREATE TABLE {quote_identifier(merged_table)} ({column_list})")
    row_count = 0
    for row in people_shards:
        connection.execute(
            f"INSERT INTO {quote_identifier(merged_table)} ({column_list}) "
            f"SELECT {column_list} FROM {quote_identifier(row['table_name'])}"
        )
        row_count += int(row["row_count"])

    available = {name.casefold(): name for name, _ in columns}
    for key in ("key_uuid", "key_person", "key_retro", "key_mlbam", "key_bbref", "key_fangraphs"):
        if key in available:
            index_name = f"chadwick_register_people_{key}_idx"
            connection.execute(
                f"CREATE INDEX {quote_identifier(index_name)} "
                f"ON {quote_identifier(merged_table)} ({quote_identifier(available[key])})"
            )
    _table_metadata(
        connection,
        merged_table,
        "chadwick_register",
        "people-*.csv (combined)",
        columns,
        row_count,
    )
    return {"table": merged_table, "rows": row_count}


@contextmanager
def _csv_sources(source: Path) -> Iterator[list[tuple[str, Callable[[], TextIO]]]]:
    if source.is_dir():
        files = sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.casefold() == ".csv")
        if not files:
            raise ValueError(f"No CSV files found under {source}")
        yield [
            (
                path.relative_to(source).as_posix(),
                lambda path=path: path.open("r", encoding="utf-8-sig", newline=""),
            )
            for path in files
        ]
        return
    if source.is_file() and source.suffix.casefold() == ".csv":
        yield [
            (
                source.name,
                lambda: source.open("r", encoding="utf-8-sig", newline=""),
            )
        ]
        return
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            infos = sorted(
                (info for info in archive.infolist() if not info.is_dir() and Path(info.filename).suffix.casefold() == ".csv"),
                key=lambda info: info.filename,
            )
            if not infos:
                raise ValueError(f"No CSV files found in archive {source}")
            yield [
                (
                    info.filename,
                    lambda info=info: io.TextIOWrapper(archive.open(info), encoding="utf-8-sig", newline=""),
                )
                for info in infos
            ]
        return
    raise ValueError(f"CSV source must be a directory, CSV file, or ZIP archive: {source}")


@contextmanager
def _event_sources(source: Path) -> Iterator[list[tuple[str, Callable[[], TextIO]]]]:
    if source.is_dir():
        files = sorted(path for path in source.rglob("*") if path.is_file() and EVENT_FILE.search(path.name))
        if not files:
            raise ValueError(f"No Retrosheet .EV? or .ED? event files found under {source}")
        yield [
            (
                path.relative_to(source).as_posix(),
                lambda path=path: path.open("r", encoding="ascii", errors="replace", newline=None),
            )
            for path in files
        ]
        return
    if source.is_file() and EVENT_FILE.search(source.name):
        yield [
            (
                source.name,
                lambda: source.open("r", encoding="ascii", errors="replace", newline=None),
            )
        ]
        return
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            infos = sorted(
                (info for info in archive.infolist() if not info.is_dir() and EVENT_FILE.search(Path(info.filename).name)),
                key=lambda info: info.filename,
            )
            if not infos:
                raise ValueError(f"No Retrosheet event files found in archive {source}")
            yield [
                (
                    info.filename,
                    lambda info=info: io.TextIOWrapper(archive.open(info), encoding="ascii", errors="replace", newline=None),
                )
                for info in infos
            ]
        return
    raise ValueError(f"Retrosheet source must be a directory, event file, or ZIP archive: {source}")


def import_csv_dataset(
    database: str | Path,
    directory: str | Path,
    dataset_id: str,
    *,
    display_name: str | None = None,
    source_url: str | None = None,
    license_text: str | None = None,
    source_version: str | None = None,
) -> dict[str, Any]:
    """Import CSV files from a directory, one CSV, or a ZIP archive into source-prefixed tables."""
    root = Path(directory).expanduser().resolve()
    prefix = _table_prefix(dataset_id)
    connection = open_database(database)
    imported_tables: list[dict[str, Any]] = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        _replace_dataset(connection, dataset_id)
        _register_dataset(connection, dataset_id, display_name, source_url, license_text, source_version)
        with _csv_sources(root) as sources:
            names: set[str] = set()
            for source_name, opener in sources:
                table_name = f"{prefix}_{_slug(Path(source_name).stem)}"
                if table_name.casefold() in names:
                    raise ValueError(f"More than one CSV maps to table {table_name}; rename or separate the files")
                names.add(table_name.casefold())
                with opener() as stream:
                    reader = csv.reader(stream)
                    headers = next(reader, None)
                    if headers is None:
                        raise ValueError(f"CSV file is empty: {source_name}")
                    columns = _safe_columns(headers)
                    quoted_columns = ", ".join(quote_identifier(name) for name, _ in columns)
                    connection.execute(f"CREATE TABLE {quote_identifier(table_name)} ({quoted_columns})")
                    placeholders = ", ".join("?" for _ in columns)
                    insert_sql = f"INSERT INTO {quote_identifier(table_name)} VALUES ({placeholders})"
                    batch: list[tuple[Any, ...]] = []
                    row_count = 0
                    for line_number, row in enumerate(reader, start=2):
                        if not row:
                            continue
                        if len(row) != len(columns):
                            raise ValueError(
                                f"{source_name}:{line_number}: expected {len(columns)} fields, found {len(row)}"
                            )
                        batch.append(tuple(_typed_cell(cell) for cell in row))
                        if len(batch) >= 2000:
                            connection.executemany(insert_sql, batch)
                            row_count += len(batch)
                            batch.clear()
                    if batch:
                        connection.executemany(insert_sql, batch)
                        row_count += len(batch)
                source_table = str(Path(source_name).with_suffix(""))
                _table_metadata(connection, table_name, dataset_id, source_table, columns, row_count)
                imported_tables.append({"table": table_name, "rows": row_count})
        if dataset_id == "chadwick_register":
            merged = _consolidate_chadwick_people(connection)
            if merged is not None:
                imported_tables.append(merged)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"dataset": dataset_id, "tables": imported_tables, "table_count": len(imported_tables)}


def _add_info(info: dict[str, Any], key: str, value: str) -> None:
    if key not in info:
        info[key] = value
    elif isinstance(info[key], list):
        info[key].append(value)
    else:
        info[key] = [info[key], value]


def _finish_game(
    connection: sqlite3.Connection,
    game_id: str | None,
    info: dict[str, Any],
    record_count: int,
) -> None:
    if game_id is not None:
        connection.execute(
            "UPDATE retrosheet_events_games SET info_json = ?, record_count = ? WHERE game_id = ?",
            (json.dumps(info, ensure_ascii=False), record_count, game_id),
        )


def import_retrosheet_events(
    database: str | Path,
    directory: str | Path,
    *,
    source_version: str | None = None,
) -> dict[str, Any]:
    """Import Retrosheet EV/ED files from a directory or ZIP, retaining raw lines and parsed game/play fields."""
    root = Path(directory).expanduser().resolve()
    connection = open_database(database)
    play_columns = [
        ("game_id", "game_id"),
        ("play_no", "play_no"),
        ("inning", "inning"),
        ("batting_team", "batting_team"),
        ("batter_id", "batter_id"),
        ("count", "count"),
        ("pitches", "pitches"),
        ("event_text", "event_text"),
        ("source_file", "source_file"),
        ("raw_record", "raw_record"),
    ]
    game_columns = [("game_id", "game_id"), ("source_file", "source_file"), ("season", "season"), ("info_json", "info_json"), ("record_count", "record_count")]
    record_columns = [("game_id", "game_id"), ("record_no", "record_no"), ("record_type", "record_type"), ("payload", "payload"), ("source_file", "source_file"), ("raw_record", "raw_record")]
    header_columns = [("source_file", "source_file"), ("record_no", "record_no"), ("record_type", "record_type"), ("payload", "payload"), ("raw_record", "raw_record")]
    counters = {"games": 0, "headers": 0, "records": 0, "plays": 0}
    try:
        connection.execute("BEGIN IMMEDIATE")
        _replace_dataset(connection, "retrosheet_events")
        _register_dataset(connection, "retrosheet_events", None, None, None, source_version)
        connection.execute(
            "CREATE TABLE retrosheet_events_games(game_id TEXT PRIMARY KEY, source_file TEXT NOT NULL, season INTEGER, info_json TEXT NOT NULL, record_count INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE retrosheet_events_records(game_id TEXT NOT NULL, record_no INTEGER NOT NULL, record_type TEXT NOT NULL, payload TEXT NOT NULL, source_file TEXT NOT NULL, raw_record TEXT NOT NULL, PRIMARY KEY(game_id, record_no))"
        )
        connection.execute(
            "CREATE TABLE retrosheet_events_file_headers(source_file TEXT NOT NULL, record_no INTEGER NOT NULL, record_type TEXT NOT NULL, payload TEXT NOT NULL, raw_record TEXT NOT NULL, PRIMARY KEY(source_file, record_no))"
        )
        connection.execute(
            "CREATE TABLE retrosheet_events_plays(game_id TEXT NOT NULL, play_no INTEGER NOT NULL, inning INTEGER NOT NULL, batting_team INTEGER NOT NULL, batter_id TEXT NOT NULL, count TEXT NOT NULL, pitches TEXT NOT NULL, event_text TEXT NOT NULL, source_file TEXT NOT NULL, raw_record TEXT NOT NULL, PRIMARY KEY(game_id, play_no))"
        )

        insert_record = "INSERT INTO retrosheet_events_records VALUES (?, ?, ?, ?, ?, ?)"
        insert_header = "INSERT INTO retrosheet_events_file_headers VALUES (?, ?, ?, ?, ?)"
        insert_play = "INSERT INTO retrosheet_events_plays VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        record_batch: list[tuple[Any, ...]] = []
        play_batch: list[tuple[Any, ...]] = []
        with _event_sources(root) as sources:
            for relative, opener in sources:
                season_match = re.match(r"^(\d{4})", Path(relative).name)
                season = int(season_match.group(1)) if season_match else None
                game_id: str | None = None
                info: dict[str, Any] = {}
                record_no = 0
                play_no = 0
                with opener() as stream:
                    for line_number, line in enumerate(stream, start=1):
                        raw = line.rstrip("\r\n")
                        if not raw:
                            continue
                        record_type, separator, payload = raw.partition(",")
                        if record_type == "id":
                            _finish_game(connection, game_id, info, record_no)
                            game_id = payload.strip() if separator else ""
                            if not game_id:
                                raise ValueError(f"{relative}:{line_number}: empty game id")
                            info = {}
                            record_no = 0
                            play_no = 0
                            connection.execute(
                                "INSERT INTO retrosheet_events_games(game_id, source_file, season, info_json, record_count) VALUES (?, ?, ?, '{}', 0)",
                                (game_id, relative, season),
                            )
                            counters["games"] += 1
                        elif game_id is None:
                            connection.execute(
                                insert_header,
                                (relative, line_number, record_type, payload if separator else "", raw),
                            )
                            counters["headers"] += 1
                            continue

                        if game_id is None:
                            continue
                        record_no += 1
                        record_batch.append((game_id, record_no, record_type, payload if separator else "", relative, raw))
                        counters["records"] += 1
                        if len(record_batch) >= 2000:
                            connection.executemany(insert_record, record_batch)
                            record_batch.clear()
                        if record_type == "info":
                            fields = raw.split(",", 2)
                            if len(fields) == 3:
                                _add_info(info, fields[1], fields[2])
                        elif record_type == "play":
                            fields = raw.split(",", 6)
                            if len(fields) != 7:
                                raise ValueError(f"{relative}:{line_number}: malformed play record")
                            try:
                                inning = int(fields[1])
                                batting_team = int(fields[2])
                            except ValueError as error:
                                raise ValueError(f"{relative}:{line_number}: invalid inning or batting-team value") from error
                            if inning < 1 or batting_team not in (0, 1):
                                raise ValueError(f"{relative}:{line_number}: inning must be positive and batting team must be 0 or 1")
                            play_no += 1
                            play_batch.append((game_id, play_no, inning, batting_team, fields[3], fields[4], fields[5], fields[6], relative, raw))
                            counters["plays"] += 1
                            if len(play_batch) >= 2000:
                                connection.executemany(insert_play, play_batch)
                                play_batch.clear()
                _finish_game(connection, game_id, info, record_no)

        if record_batch:
            connection.executemany(insert_record, record_batch)
        if play_batch:
            connection.executemany(insert_play, play_batch)

        connection.execute("CREATE INDEX retrosheet_events_plays_batter_idx ON retrosheet_events_plays(batter_id)")
        connection.execute("CREATE INDEX retrosheet_events_games_season_idx ON retrosheet_events_games(season)")
        for table_name, source_table, columns, key in (
            ("retrosheet_events_games", "games", game_columns, "games"),
            ("retrosheet_events_file_headers", "file_headers", header_columns, "headers"),
            ("retrosheet_events_records", "records", record_columns, "records"),
            ("retrosheet_events_plays", "plays", play_columns, "plays"),
        ):
            _table_metadata(connection, table_name, "retrosheet_events", source_table, columns, counters[key])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"dataset": "retrosheet_events", **counters}
