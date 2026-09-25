from __future__ import annotations

import csv
import tempfile
import zipfile
from pathlib import Path

from verify_support import call_tool, content_json, initialize, start_server
from baseball_mcp.ingest import import_csv_dataset


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lahman-verify-") as temporary:
        root = Path(temporary)
        people = root / "People.csv"
        with people.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["playerID", "nameFirst", "nameLast"])
            writer.writerow(["sample01", "Casey", "Rookie"])
        batting_post = root / "BattingPost.csv"
        with batting_post.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["playerID", "yearID", "HR", "RBI"])
            writer.writerow(["sample01", "2025", "12", "31"])

        archive = root / "lahman-csv.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(people, "lahman/People.csv")
            bundle.write(batting_post, "lahman/BattingPost.csv")
        database = root / "lahman.sqlite3"
        outcome = import_csv_dataset(database, archive, "lahman", source_version="2025-test")
        assert outcome["table_count"] == 2
        assert {table["table"] for table in outcome["tables"]} == {"lahman_people", "lahman_batting_post"}
        client = start_server(database)
        try:
            initialize(client)
            catalog = content_json(call_tool(client, "list_datasets"))["datasets"]
            lahman = next(item for item in catalog if item["id"] == "lahman")
            assert lahman["installation"]["source_version"] == "2025-test"
            tables = content_json(call_tool(client, "list_tables", {"dataset_id": "lahman"}))["tables"]
            assert len(tables) == 2
            description = content_json(call_tool(client, "describe_table", {"table_name": "lahman_batting_post"}))
            assert description["row_count"] == 1
            query = content_json(call_tool(client, "query_sql", {"sql": "SELECT playerID, yearID, HR FROM lahman_batting_post"}))
            assert query["rows"] == [["sample01", 2025, 12]]
        finally:
            client.close()
    print("Lahman import verification passed")


if __name__ == "__main__":
    main()
