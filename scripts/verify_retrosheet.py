from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from verify_support import call_tool, content_json, initialize, start_server
from baseball_mcp.ingest import import_retrosheet_events


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="retrosheet-verify-") as temporary:
        root = Path(temporary)
        event_file = root / "2024ANA.EVN"
        event_file.write_text(
            "version,2\n"
            "id,ANA202404010\n"
            "info,visteam,OAK\n"
            "info,hometeam,LAA\n"
            "start,player01,Sample Batter,0,1,1\n"
            "play,1,0,player01,00,,S7/G.3-H;2-3\n"
            "com,source comment, preserved\n"
            "data,er,0\n",
            encoding="ascii",
        )
        archive = root / "retrosheet-eventfiles.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(event_file, "2024/2024ANA.EVN")
        database = root / "retrosheet.sqlite3"
        outcome = import_retrosheet_events(database, archive)
        assert outcome == {"dataset": "retrosheet_events", "games": 1, "headers": 1, "records": 7, "plays": 1}
        client = start_server(database)
        try:
            initialize(client)
            header = content_json(call_tool(client, "query_sql", {"sql": "SELECT record_type, raw_record FROM retrosheet_events_file_headers"}))
            assert header["rows"] == [["version", "version,2"]]
            game = content_json(call_tool(client, "query_sql", {"sql": "SELECT game_id, season, info_json, record_count FROM retrosheet_events_games"}))
            assert game["rows"][0][0] == "ANA202404010"
            assert game["rows"][0][1] == 2024
            assert json.loads(game["rows"][0][2]) == {"visteam": "OAK", "hometeam": "LAA"}
            play = content_json(call_tool(client, "query_sql", {"sql": "SELECT inning, batting_team, batter_id, event_text, raw_record FROM retrosheet_events_plays"}))
            assert play["rows"][0] == [1, 0, "player01", "S7/G.3-H;2-3", "play,1,0,player01,00,,S7/G.3-H;2-3"]
            raw = content_json(call_tool(client, "query_sql", {"sql": "SELECT raw_record FROM retrosheet_events_records WHERE record_type = 'com'"}))
            assert raw["rows"] == [["com,source comment, preserved"]]
        finally:
            client.close()
    print("Retrosheet import verification passed")


if __name__ == "__main__":
    main()
