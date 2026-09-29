"""Public source catalog and attribution notes."""

from __future__ import annotations

from typing import Any


DATASETS: list[dict[str, Any]] = [
    {
        "id": "lahman",
        "name": "SABR Lahman Baseball Database",
        "description": "Historical batting, pitching, fielding, teams, awards, and related tables distributed as CSV.",
        "url": "https://sabr.org/lahman-database/",
        "format": "CSV or ZIP containing CSV files",
        "license": "See the notices and license in the exact release supplied by the user. The current SABR page describes the release and download formats; this server does not redistribute Lahman files.",
    },
    {
        "id": "retrosheet_events",
        "name": "Retrosheet event files",
        "description": "Game event files with game metadata and play-by-play scoring records; source record content is retained.",
        "url": "https://www.retrosheet.org/game.htm",
        "format": "Directory, single event file, or ZIP containing .EVA/.EVN/.EVF/.EVR and .EDA/.EDN/.EDF/.EDR text files",
        "license": "When transferring Retrosheet data or products based on it, prominently include: The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at 20 Sunset Rd., Newark, DE 19711.",
    },
    {
        "id": "retrosheet_csv",
        "name": "Retrosheet processed CSV files",
        "description": "Retrosheet daily-log and parsed play-by-play CSV releases, loaded as source-prefixed tables.",
        "url": "https://www.retrosheet.org/downloads/csvdownloads.html",
        "format": "CSV or ZIP containing CSV files",
        "license": "Retain the Retrosheet attribution required for transferred data; consult the source page for the exact files and limitations.",
    },
    {
        "id": "chadwick_register",
        "name": "Chadwick Baseball Bureau Persons Register",
        "description": "Public baseball-person identity files and cross-references, including Retrosheet, MLBAM, Baseball-Reference, and FanGraphs identifiers.",
        "url": "https://github.com/chadwickbureau/register",
        "format": "CSV or ZIP containing CSV files",
        "license": "Open Data Commons Attribution License (ODC-BY) 1.0; follow the repository's attribution requirements.",
    },
    {
        "id": "chadwick_retrosplits",
        "name": "Chadwick Retrosplits",
        "description": "Public splits and day-by-day tables derived from Retrosheet data.",
        "url": "https://github.com/chadwickbureau/retrosplits",
        "format": "CSV files; use the generic CSV importer.",
        "license": "The repository identifies the database under the Open Database License (ODbL) and individual contents under the Database Contents License (DBCL); retain its Retrosheet attribution as well.",
    },
    {
        "id": "statcast_csv",
        "name": "MLB Statcast Search CSV",
        "description": "Pitch-, game-, player-, team-, and season-level Statcast Search exports from Baseball Savant.",
        "url": "https://baseballsavant.mlb.com/statcast_search",
        "format": "CSV export from a Baseball Savant search",
        "license": "Follow the current MLB/Baseball Savant terms. This catalog does not assign a separate data license; retain the export context and query filters.",
    },
    {
        "id": "openbiomechanics_pitching",
        "name": "OpenBiomechanics Project — Baseball Pitching",
        "description": "CSV point-of-interest metrics, metadata, and any additional CSV files in the local pitching data directory. This catalog entry does not download or include OBP data.",
        "url": "https://github.com/drivelineresearch/openbiomechanics/tree/main/baseball_pitching",
        "format": "CSV files in baseball_pitching/data",
        "license": "Data and biomechanics documentation are CC BY-NC-SA 4.0 with an additional exclusion prohibiting any use by employees or contractors employed by, associated with, or significant shareholders of professional sports organizations or financial analysis firms without a separate written paid license. Review LICENSE-DATA.md in the exact upstream release before use. Code has a separate MIT license.",
    },
    {
        "id": "openbiomechanics_hitting",
        "name": "OpenBiomechanics Project — Baseball Hitting",
        "description": "CSV point-of-interest metrics, metadata, HitTrax records, and any additional CSV files in the local hitting data directory. This catalog entry does not download or include OBP data.",
        "url": "https://github.com/drivelineresearch/openbiomechanics/tree/main/baseball_hitting",
        "format": "CSV files in baseball_hitting/data",
        "license": "Data and biomechanics documentation are CC BY-NC-SA 4.0 with an additional exclusion prohibiting any use by employees or contractors employed by, associated with, or significant shareholders of professional sports organizations or financial analysis firms without a separate written paid license. Review LICENSE-DATA.md in the exact upstream release before use. Code has a separate MIT license.",
    },
    {
        "id": "openbiomechanics_high_performance",
        "name": "OpenBiomechanics Project — High Performance",
        "description": "CSV high-performance force-plate and physical-assessment metrics from the local OBP release. This catalog entry does not download or include OBP data.",
        "url": "https://github.com/drivelineresearch/openbiomechanics/tree/main/high_performance",
        "format": "CSV files in high_performance/data",
        "license": "Data and biomechanics documentation are CC BY-NC-SA 4.0 with an additional exclusion prohibiting any use by employees or contractors employed by, associated with, or significant shareholders of professional sports organizations or financial analysis firms without a separate written paid license. Review LICENSE-DATA.md in the exact upstream release before use. Code has a separate MIT license.",
    },
    {
        "id": "custom",
        "name": "Other public CSV dataset",
        "description": "User-supplied CSV tables from another public source. Its source and license must be recorded by the operator.",
        "url": None,
        "format": "CSV",
        "license": "User supplied; verify the source terms and provide --url and --license when importing.",
    },
]

DATASET_BY_ID = {dataset["id"]: dataset for dataset in DATASETS}


def catalog_with_install_state(connection: Any | None) -> dict[str, Any]:
    installed: dict[str, dict[str, Any]] = {}
    if connection is not None:
        try:
            rows = connection.execute(
                "SELECT dataset_id, display_name, source_url, license, imported_at, source_version "
                "FROM _baseball_mcp_datasets ORDER BY dataset_id"
            ).fetchall()
            installed = {
                row["dataset_id"]: {
                    "display_name": row["display_name"],
                    "source_url": row["source_url"],
                    "license": row["license"],
                    "imported_at": row["imported_at"],
                    "source_version": row["source_version"],
                }
                for row in rows
            }
        except Exception:
            installed = {}

    datasets = []
    for source in DATASETS:
        item = dict(source)
        item["installed"] = item["id"] in installed
        item["installation"] = installed.get(item["id"])
        datasets.append(item)
    for dataset_id, info in installed.items():
        if dataset_id not in DATASET_BY_ID:
            datasets.append(
                {
                    "id": dataset_id,
                    "name": info["display_name"] or dataset_id,
                    "description": "User-registered CSV dataset.",
                    "url": info["source_url"],
                    "format": "CSV",
                    "license": info["license"],
                    "installed": True,
                    "installation": info,
                }
            )
    return {"datasets": datasets}
