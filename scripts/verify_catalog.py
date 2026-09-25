from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from verify_support import call_tool, content_json, initialize, start_server
from baseball_mcp.catalog import DATASET_BY_ID
from baseball_mcp.ingest import import_csv_dataset


def main() -> None:
    assert "ODC-BY" in DATASET_BY_ID["chadwick_register"]["license"]
    assert "Retrosheet" in DATASET_BY_ID["retrosheet_events"]["license"]
    assert "retrosheet.org/downloads/csvdownloads.html" in DATASET_BY_ID["retrosheet_csv"]["url"]
    assert DATASET_BY_ID["chadwick_retrosplits"]["url"].endswith("chadwickbureau/retrosplits")
    assert DATASET_BY_ID["chadwick_retrosplits"]["license"].count("ODbL") == 1
    assert DATASET_BY_ID["statcast_csv"]["url"] == "https://baseballsavant.mlb.com/statcast_search"
    assert "CSV" in DATASET_BY_ID["statcast_csv"]["format"]
    with tempfile.TemporaryDirectory(prefix="chadwick-verify-") as temporary:
        root = Path(temporary)
        source = root / "register"
        source.mkdir()
        with (source / "people-a.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["key_uuid", "key_person", "key_retro", "key_mlbam", "key_bbref", "key_fangraphs", "name_first", "name_last"])
            writer.writerow(["uuid-1", "short1", "sample01", "123", "casey01", "1001", "Casey", "Rookie"])
        with (source / "people-b.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["key_uuid", "key_person", "key_retro", "key_mlbam", "key_bbref", "key_fangraphs", "name_first", "name_last"])
            writer.writerow(["uuid-2", "short2", "sample02", "456", "riley01", "1002", "Riley", "Pitcher"])
        database = root / "baseball.sqlite3"
        import_csv_dataset(database, source, "chadwick_register")
        statcast_export = root / "statcast.csv"
        with statcast_export.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["game_date", "player_name", "batter", "pitcher", "pitch_type"])
            writer.writerow(["2025-04-01", "Casey Rookie", "123", "456", "FF"])
        import_csv_dataset(
            database,
            statcast_export,
            "statcast_csv",
            source_url="https://baseballsavant.mlb.com/statcast_search?test-query",
            license_text="Use under source terms",
            source_version="2025-test-query",
        )
        client = start_server(database)
        try:
            initialize(client)
            catalog = content_json(call_tool(client, "list_datasets"))["datasets"]
            register = next(item for item in catalog if item["id"] == "chadwick_register")
            assert register["installed"] is True
            assert "ODC-BY" in register["installation"]["license"]
            tables = content_json(call_tool(client, "list_tables", {"dataset_id": "chadwick_register"}))["tables"]
            assert [table["table_name"] for table in tables] == [
                "chadwick_register_people",
                "chadwick_register_people_a",
                "chadwick_register_people_b",
            ]
            people = content_json(
                call_tool(client, "query_sql", {"sql": "SELECT COUNT(*) FROM chadwick_register_people"})
            )
            assert people["rows"] == [[2]]
            indexes = content_json(
                call_tool(
                    client,
                    "query_sql",
                    {"sql": "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'chadwick_register_people_%_idx' ORDER BY name"},
                )
            )
            assert {row[0] for row in indexes["rows"]} >= {
                "chadwick_register_people_key_retro_idx",
                "chadwick_register_people_key_mlbam_idx",
                "chadwick_register_people_key_bbref_idx",
            }
            statcast = next(item for item in catalog if item["id"] == "statcast_csv")
            assert statcast["installed"] is True
            assert statcast["installation"]["source_url"].endswith("?test-query")
            assert statcast["installation"]["source_version"] == "2025-test-query"
            statcast_tables = content_json(call_tool(client, "list_tables", {"dataset_id": "statcast_csv"}))["tables"]
            assert [table["table_name"] for table in statcast_tables] == ["statcast_csv_statcast"]
            joined = content_json(
                call_tool(
                    client,
                    "query_sql",
                    {
                        "sql": "SELECT r.key_retro, s.player_name FROM chadwick_register_people AS r "
                        "JOIN statcast_csv_statcast AS s ON r.key_mlbam = s.batter WHERE r.key_retro = 'sample01'"
                    },
                )
            )
            assert joined["rows"] == [["sample01", "Casey Rookie"]]
        finally:
            client.close()
    print("dataset catalog verification passed")


if __name__ == "__main__":
    main()
