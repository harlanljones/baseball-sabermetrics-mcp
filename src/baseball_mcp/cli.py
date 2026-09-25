"""Command-line ingestion entry point."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Sequence

from .ingest import default_database_path, import_csv_dataset, import_retrosheet_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="baseball-sabermetrics",
        description="Import public baseball CSV and Retrosheet event files into a local SQLite database.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest = subparsers.add_parser("ingest", help="import a local dataset")
    kinds = ingest.add_subparsers(dest="kind", required=True)

    lahman = kinds.add_parser("lahman", help="import the CSV files from a SABR Lahman release")
    lahman.add_argument("source", dest="source_path", type=Path, help="directory, CSV file, or ZIP archive containing Lahman CSV files")
    lahman.add_argument("--db", type=Path, default=None, help="SQLite output path (default: BASEBALL_MCP_DB or data/baseball.sqlite3)")
    lahman.add_argument("--version", dest="source_version", help="release/version label recorded with the imported data")

    retrosheet = kinds.add_parser("retrosheet", help="import extracted Retrosheet .EV? and .ED? event files")
    retrosheet.add_argument("source", dest="source_path", type=Path, help="directory, event file, or ZIP archive containing event files")
    retrosheet.add_argument("--db", type=Path, default=None, help="SQLite output path (default: BASEBALL_MCP_DB or data/baseball.sqlite3)")
    retrosheet.add_argument("--version", dest="source_version", help="release/version label recorded with the imported data")

    csv_parser = kinds.add_parser("csv", help="import CSV tables from another listed public source")
    csv_parser.add_argument("source_id", help="catalog id such as chadwick_register, chadwick_retrosplits, statcast_csv, retrosheet_csv, or custom")
    csv_parser.add_argument("source", dest="source_path", type=Path, help="directory, CSV file, or ZIP archive containing CSV files")
    csv_parser.add_argument("--db", type=Path, default=None, help="SQLite output path (default: BASEBALL_MCP_DB or data/baseball.sqlite3)")
    csv_parser.add_argument("--name", dest="display_name", help="display name for a custom source")
    csv_parser.add_argument("--url", dest="source_url", help="source URL or export query URL to retain in the catalog")
    csv_parser.add_argument("--license", dest="license_text", help="source license or reuse terms to record")
    csv_parser.add_argument("--version", dest="source_version", help="release/query label recorded with the imported data")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = args.db or default_database_path()
    try:
        if args.kind == "lahman":
            result = import_csv_dataset(database, args.source_path, "lahman", source_version=args.source_version)
        elif args.kind == "retrosheet":
            result = import_retrosheet_events(database, args.source_path, source_version=args.source_version)
        elif args.kind == "csv":
            result = import_csv_dataset(
                database,
                args.source_path,
                args.source_id,
                display_name=args.display_name,
                source_url=args.source_url,
                license_text=args.license_text,
                source_version=args.source_version,
            )
        else:
            raise ValueError(f"Unsupported ingestion kind: {args.kind}")
        print(json.dumps({"database": str(database.expanduser().resolve()), **result}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, csv.Error, zipfile.BadZipFile, sqlite3.Error) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
