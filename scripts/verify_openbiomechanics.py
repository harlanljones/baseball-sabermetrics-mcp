from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseball_mcp.catalog import DATASET_BY_ID, catalog_with_install_state
from baseball_mcp.ingest import import_csv_dataset, open_database


def main() -> None:
    ids = (
        "openbiomechanics_pitching",
        "openbiomechanics_hitting",
        "openbiomechanics_high_performance",
    )
    for dataset_id in ids:
        item = DATASET_BY_ID[dataset_id]
        assert item["url"].startswith("https://github.com/drivelineresearch/openbiomechanics/")
        assert "CC BY-NC-SA 4.0" in item["license"]
        assert "professional sports organizations" in item["license"]
        assert "financial analysis firms" in item["license"]
        assert "paid license" in item["license"]

    with tempfile.TemporaryDirectory(prefix="baseball-obp-verify-") as temporary:
        root = Path(temporary)
        module_data = root / "baseball_pitching" / "data"
        module_data.mkdir(parents=True)
        with (module_data / "poi_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["session_pitch", "pitch_speed_mph"])
            writer.writerow(["fixture-1", 88.5])
        database = root / "test.sqlite3"
        result = import_csv_dataset(database, module_data, ids[0], source_version="fixture-release")
        assert result["dataset"] == ids[0]
        assert {table["table"] for table in result["tables"]} == {"openbiomechanics_pitching_poi_metrics"}

        connection = open_database(database)
        try:
            installed = {
                item["id"]: item
                for item in catalog_with_install_state(connection)["datasets"]
            }[ids[0]]
            assert installed["installed"] is True
            assert installed["installation"]["source_version"] == "fixture-release"
            assert "CC BY-NC-SA 4.0" in installed["installation"]["license"]
            assert connection.execute(
                "SELECT session_pitch FROM openbiomechanics_pitching_poi_metrics"
            ).fetchone()[0] == "fixture-1"
        finally:
            connection.close()

    print("OpenBiomechanics integration verification passed")


if __name__ == "__main__":
    main()
