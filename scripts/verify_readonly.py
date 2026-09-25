from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from verify_support import call_tool, content_json, initialize, start_server
from baseball_mcp.ingest import import_csv_dataset


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="readonly-verify-") as temporary:
        root = Path(temporary)
        source = root / "lahman"
        source.mkdir()
        with (source / "People.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["playerID", "nameFirst"])
            writer.writerow(["sample01", "Casey"])
        database = root / "baseball.sqlite3"
        import_csv_dataset(database, source, "lahman")
        client = start_server(database)
        try:
            initialize(client)
            selected = call_tool(client, "query_sql", {"sql": "WITH candidates AS (SELECT playerID FROM lahman_people) SELECT playerID FROM candidates"})
            assert selected["isError"] is False
            assert content_json(selected)["rows"] == [["sample01"]]
            for sql in (
                "INSERT INTO lahman_people(playerID, nameFirst) VALUES ('new01', 'New')",
                "PRAGMA table_info(lahman_people)",
                "ATTACH DATABASE ':memory:' AS another",
            ):
                rejected = call_tool(client, "query_sql", {"sql": sql})
                assert rejected["isError"] is True, sql
            unchanged = content_json(call_tool(client, "query_sql", {"sql": "SELECT COUNT(*) AS n FROM lahman_people"}))
            assert unchanged["rows"] == [[1]]
        finally:
            client.close()

        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        assert "query_sql" in readme
        assert "The information used here was obtained free of charge from and is copyrighted by Retrosheet." in readme
        assert "BASEBALL_MCP_DB" in readme
    print("read-only verification passed")


if __name__ == "__main__":
    main()
