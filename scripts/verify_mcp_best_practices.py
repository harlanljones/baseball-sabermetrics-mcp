from __future__ import annotations

import json
import tempfile
from pathlib import Path

from verify_support import call_tool, initialize, start_server
from baseball_mcp.ingest import open_database
from baseball_mcp.server import MAX_REQUEST_BYTES, RESOURCES, TOOLS

MODERN_METADATA = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "verification-client", "version": "1"},
}


def main() -> None:
    assert len(TOOLS) == 4
    for tool in TOOLS:
        assert tool["inputSchema"].get("additionalProperties") is False
        assert tool["outputSchema"]["type"] == "object"
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False
        assert tool["annotations"]["idempotentHint"] is True
        assert tool["annotations"]["openWorldHint"] is False

    with tempfile.TemporaryDirectory(prefix="baseball-mcp-guidance-") as temporary:
        database = Path(temporary) / "example.sqlite3"
        connection = open_database(database)
        try:
            connection.execute("CREATE TABLE fixture (name TEXT, runs INTEGER)")
            connection.execute("CREATE TABLE fixture_two (name TEXT)")
            connection.execute("CREATE TABLE fixture_three (name TEXT)")
            connection.execute("INSERT INTO fixture VALUES ('sample', 9)")
        finally:
            connection.close()

        client = start_server(database)
        try:
            initialize(client)
            advertised = client.request("tools/list")["result"]["tools"]
            assert advertised == TOOLS
            listed_resources = client.request("resources/list")["result"]["resources"]
            assert listed_resources == RESOURCES

            result = call_tool(client, "query_sql", {"sql": "SELECT name, runs FROM fixture", "limit": 1})
            assert result.get("isError") is False
            structured = result["structuredContent"]
            assert structured == {"columns": ["name", "runs"], "rows": [["sample", 9]], "truncated": False}
            assert json.loads(result["content"][0]["text"]) == structured

            malformed = call_tool(client, "query_sql", {"sql": "SELECT 1", "limit": True})
            assert malformed.get("isError") is True
            unexpected = call_tool(client, "list_datasets", {"source": "elsewhere"})
            assert unexpected.get("isError") is True
            denied = call_tool(client, "query_sql", {"sql": "DELETE FROM fixture"})
            assert denied.get("isError") is True
            missing = client.request("resources/read", {"uri": "baseball://not-a-resource"})
            assert missing["error"]["code"] == -32002
            malformed_initialize = client.request("initialize", {"protocolVersion": "2025-11-25"})
            assert malformed_initialize["error"]["code"] == -32602

            first_page = call_tool(client, "list_tables", {"limit": 1, "offset": 0})["structuredContent"]
            assert first_page["total_count"] == 3 and first_page["next_offset"] == 1

            assert client.process.stdin is not None and client.process.stdout is not None
            oversized = '{"jsonrpc":"2.0","id":999,"method":"ping","params":{}}' + (" " * MAX_REQUEST_BYTES) + "\n"
            client.process.stdin.write(oversized)
            client.process.stdin.flush()
            too_large = json.loads(client.process.stdout.readline())
            assert too_large["error"]["code"] == -32600

        finally:
            client.close()

        modern_client = start_server(database)
        try:
            missing_meta = modern_client.request("tools/list")
            assert missing_meta["error"]["code"] == -32602
            discovery = modern_client.request("server/discover", {"_meta": MODERN_METADATA})["result"]
            assert discovery["resultType"] == "complete"
            assert discovery["supportedVersions"] == ["2026-07-28", "2025-11-25", "2025-06-18"]
            modern_request = {"_meta": MODERN_METADATA}
            modern_tools = modern_client.request("tools/list", modern_request)["result"]
            assert modern_tools["resultType"] == "complete"
            assert modern_tools["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "baseball-sabermetrics-mcp"
            modern_call = modern_client.request(
                "tools/call",
                {**modern_request, "name": "query_sql", "arguments": {"sql": "SELECT 1 AS ok"}},
            )["result"]
            assert modern_call["resultType"] == "complete"
            assert modern_call["structuredContent"]["rows"] == [[1]]
            modern_missing_resource = modern_client.request(
                "resources/read", {**modern_request, "uri": "baseball://not-a-resource"}
            )
            assert modern_missing_resource["error"]["code"] == -32602
            malformed_client_info = {
                "_meta": {**MODERN_METADATA, "io.modelcontextprotocol/clientInfo": {"name": "missing-version"}}
            }
            assert modern_client.request("tools/list", malformed_client_info)["error"]["code"] == -32602
            unsupported = {
                "_meta": {
                    **MODERN_METADATA,
                    "io.modelcontextprotocol/protocolVersion": "1900-01-01",
                }
            }
            unsupported_response = modern_client.request("tools/list", unsupported)["error"]
            assert unsupported_response["code"] == -32022
            assert unsupported_response["data"]["supported"] == ["2026-07-28", "2025-11-25", "2025-06-18"]
            unknown_tool = modern_client.request("tools/call", {**modern_request, "name": "missing", "arguments": {}})
            assert unknown_tool["error"]["code"] == -32602
        finally:
            modern_client.close()

    print("MCP best-practices verification passed")


if __name__ == "__main__":
    main()
