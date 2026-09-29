"""Generate or verify the public machine-readable MCP interface reference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseball_mcp import __version__  # noqa: E402
from baseball_mcp.server import (  # noqa: E402
    LEGACY_PROTOCOLS,
    MAX_QUERY_LENGTH,
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    MODERN_PROTOCOLS,
    QUERY_TIME_LIMIT_SECONDS,
    RESOURCES,
    SUPPORTED_PROTOCOLS,
    TOOL_CALLS_PER_MINUTE,
    TOOLS,
)

OUTPUT = ROOT / "docs" / "mcp-interface.json"

_QUERY_ROW_LIMIT = next(
    tool for tool in TOOLS if tool["name"] == "query_sql"
)["inputSchema"]["properties"]["limit"]["maximum"]


def interface_document() -> dict[str, object]:
    return {
        "documentVersion": 1,
        "server": {
            "name": "baseball-sabermetrics-mcp",
            "version": __version__,
            "transport": "stdio",
            "encoding": "newline-delimited JSON-RPC 2.0",
            "protocolVersions": sorted(SUPPORTED_PROTOCOLS, reverse=True),
            "discovery": {
                "method": "server/discover",
                "supportedVersions": sorted(SUPPORTED_PROTOCOLS, reverse=True),
                "resultType": "complete",
            },
            "protocolModes": {
                "modernPerRequestMetadata": sorted(MODERN_PROTOCOLS, reverse=True),
                "legacyInitialization": sorted(LEGACY_PROTOCOLS, reverse=True),
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "databaseConfiguration": {
                "environmentVariable": "BASEBALL_MCP_DB",
                "defaultPath": "data/baseball.sqlite3",
                "mode": "read-only in MCP server; write access is limited to the separate importer CLI",
            },
        },
        "methods": [
            {
                "method": "server/discover",
                "kind": "request",
                "modernMetadata": ["io.modelcontextprotocol/protocolVersion", "io.modelcontextprotocol/clientCapabilities"],
                "result": ["resultType", "supportedVersions", "capabilities", "instructions", "ttlMs", "cacheScope", "_meta"],
                "errors": [-32022, -32602],
            },
            {
                "method": "initialize",
                "kind": "request",
                "request": ["protocolVersion", "capabilities", "clientInfo"],
                "result": ["protocolVersion", "capabilities", "serverInfo", "instructions"],
                "errors": [-32602, -32603],
            },
            {"method": "ping", "kind": "request", "request": [], "result": {"resultType": "complete"}, "errors": [-32602, -32603]},
            {"method": "shutdown", "kind": "request", "request": [], "result": {"resultType": "complete"}, "errors": [-32602, -32603]},
            {"method": "tools/list", "kind": "request", "request": [], "result": {"tools": "server.tools", "modernCache": ["ttlMs", "cacheScope"]}, "errors": [-32602, -32603]},
            {
                "method": "tools/call",
                "kind": "request",
                "request": ["name", "arguments"],
                "result": "MCP CallToolResult",
                "executionErrors": "isError=true with text content",
                "errors": [-32602, -32603],
            },
            {"method": "resources/list", "kind": "request", "request": [], "result": {"resources": "server.resources", "modernCache": ["ttlMs", "cacheScope"]}, "errors": [-32602, -32603]},
            {
                "method": "resources/read",
                "kind": "request",
                "request": ["uri"],
                "result": {"contents": [{"uri": "string", "mimeType": "application/json", "text": "JSON string"}]},
                "errors": {"legacy": [-32002], "modern": [-32602], "invalidParams": [-32602], "internal": [-32603]},
            },
            {"method": "notifications/initialized", "kind": "notification", "response": "none"},
        ],
        "jsonRpcErrors": [
            {"code": -32700, "name": "Parse error"},
            {"code": -32600, "name": "Invalid Request"},
            {"code": -32601, "name": "Method not found"},
            {"code": -32602, "name": "Invalid params"},
            {"code": -32603, "name": "Internal error"},
            {"code": -32022, "name": "Unsupported protocol version"},
            {"code": -32002, "name": "Resource not found", "protocolMode": "legacy only"},
        ],
        "limits": {
            "sqlCharacters": MAX_QUERY_LENGTH,
            "queryRows": _QUERY_ROW_LIMIT,
            "queryExecutionSeconds": QUERY_TIME_LIMIT_SECONDS,
            "querySerializedDataBytes": MAX_RESULT_BYTES,
            "toolCallsPerMinute": TOOL_CALLS_PER_MINUTE,
            "requestLineBytes": MAX_REQUEST_BYTES,
        },
        "tools": TOOLS,
        "resources": RESOURCES,
    }


def rendered() -> str:
    return json.dumps(interface_document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the checked-in JSON differs from the runtime interface")
    args = parser.parse_args()
    expected = rendered()
    if args.check:
        try:
            actual = OUTPUT.read_text(encoding="utf-8")
        except OSError as error:
            print(f"Cannot read {OUTPUT}: {error}", file=sys.stderr)
            return 1
        if actual != expected:
            print("MCP interface document is stale; run python scripts/export_mcp_spec.py", file=sys.stderr)
            return 1
        print("MCP interface document matches runtime definitions")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
