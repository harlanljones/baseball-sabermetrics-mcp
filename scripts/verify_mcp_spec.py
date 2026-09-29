from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseball_mcp.server import (
    MAX_QUERY_LENGTH,
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    QUERY_TIME_LIMIT_SECONDS,
    RESOURCES,
    SUPPORTED_PROTOCOLS,
    TOOL_CALLS_PER_MINUTE,
    TOOLS,
)

def main() -> None:
    document = json.loads((ROOT / "docs" / "mcp-interface.json").read_text(encoding="utf-8"))
    assert document["documentVersion"] == 1
    assert document["server"]["name"] == "baseball-sabermetrics-mcp"
    assert document["server"]["transport"] == "stdio"
    assert document["server"]["protocolVersions"] == sorted(SUPPORTED_PROTOCOLS, reverse=True)
    assert document["server"]["discovery"]["supportedVersions"] == sorted(SUPPORTED_PROTOCOLS, reverse=True)
    assert document["limits"] == {
        "sqlCharacters": MAX_QUERY_LENGTH,
        "queryRows": next(
            tool for tool in TOOLS if tool["name"] == "query_sql"
        )["inputSchema"]["properties"]["limit"]["maximum"],
        "queryExecutionSeconds": QUERY_TIME_LIMIT_SECONDS,
        "querySerializedDataBytes": MAX_RESULT_BYTES,
        "toolCallsPerMinute": TOOL_CALLS_PER_MINUTE,
        "requestLineBytes": MAX_REQUEST_BYTES,
    }
    assert document["server"]["protocolModes"]["modernPerRequestMetadata"] == ["2026-07-28"]
    assert document["tools"] == TOOLS
    assert document["resources"] == RESOURCES
    methods = {item["method"] for item in document["methods"]}
    assert methods == {
        "server/discover", "initialize", "ping", "shutdown", "tools/list", "tools/call",
        "resources/list", "resources/read", "notifications/initialized",
    }
    methods_by_name = {item["method"]: item for item in document["methods"]}
    assert methods_by_name["resources/read"]["errors"]["legacy"] == [-32002]
    assert methods_by_name["resources/read"]["errors"]["modern"] == [-32602]
    assert next(error for error in document["jsonRpcErrors"] if error["code"] == -32002)["protocolMode"] == "legacy only"
    prose = (ROOT / "docs" / "mcp-interface.md").read_text(encoding="utf-8")
    for tool in TOOLS:
        assert f"`{tool['name']}`" in prose
    for resource in RESOURCES:
        assert f"`{resource['uri']}`" in prose
    for method in methods - {"notifications/initialized"}:
        assert f"`{method}`" in prose, f"Method {method} missing from prose reference"
    print("MCP interface specification verification passed")


if __name__ == "__main__":
    main()
