from __future__ import annotations

import tempfile
from pathlib import Path

from verify_support import call_tool, content_json, initialize, start_server


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="baseball-mcp-") as temporary:
        client = start_server(Path(temporary) / "not-yet-imported.sqlite3")
        try:
            initialized = initialize(client)
            assert initialized["protocolVersion"] == "2025-11-25"
            assert initialized["capabilities"]["tools"]
            assert initialized["capabilities"]["resources"]
            tools = client.request("tools/list")["result"]["tools"]
            assert {tool["name"] for tool in tools} == {"list_datasets", "list_tables", "describe_table", "query_sql"}
            resources = client.request("resources/list")["result"]["resources"]
            assert {resource["uri"] for resource in resources} >= {"baseball://datasets", "baseball://tables", "baseball://schema"}
            sources = content_json(call_tool(client, "list_datasets"))["datasets"]
            assert {source["id"] for source in sources} >= {"lahman", "retrosheet_events", "chadwick_register"}
        finally:
            client.close()
    print("MCP protocol verification passed")


if __name__ == "__main__":
    main()

