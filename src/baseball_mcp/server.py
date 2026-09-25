"""Dependency-free MCP stdio server for read-only baseball dataset queries."""

from __future__ import annotations

import base64
import json
import math
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from .catalog import catalog_with_install_state
from .ingest import default_database_path, quote_identifier

SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
MAX_QUERY_LENGTH = 20_000
MAX_RESULT_BYTES = 450_000
QUERY_TIME_LIMIT_SECONDS = 5

TOOLS = [
    {
        "name": "list_datasets",
        "description": "List supported public baseball data sources and show which datasets are installed in the configured local SQLite database.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_tables",
        "description": "List queryable tables. Imported table names are prefixed with their source id, such as lahman_batting or retrosheet_events_plays. Optionally filter by dataset id.",
        "inputSchema": {
            "type": "object",
            "properties": {"dataset_id": {"type": "string", "description": "Optional source id such as lahman or retrosheet_events."}},
            "additionalProperties": False,
        },
    },
    {
        "name": "describe_table",
        "description": "Return columns, source table name, row count, and dataset id for a local SQLite table.",
        "inputSchema": {
            "type": "object",
            "properties": {"table_name": {"type": "string"}},
            "required": ["table_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_sql",
        "description": "Run one read-only SQLite SELECT or WITH query over the imported baseball tables. Writes, schema changes, ATTACH, and PRAGMA are denied. Results are capped by row count and response size.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "One SQLite SELECT statement or read-only CTE."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
    },
]

RESOURCES = [
    {
        "uri": "baseball://datasets",
        "name": "Supported baseball datasets",
        "description": "Supported public data sources, import formats, and source-specific attribution notes.",
        "mimeType": "application/json",
    },
    {
        "uri": "baseball://tables",
        "name": "Imported baseball tables",
        "description": "Tables available in the configured local SQLite database.",
        "mimeType": "application/json",
    },
    {
        "uri": "baseball://schema",
        "name": "Imported baseball schema",
        "description": "Table names, source columns, row counts, and dataset ids.",
        "mimeType": "application/json",
    },
]

_DENIED_SQLITE_ACTIONS = {
    getattr(sqlite3, name)
    for name in (
        "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE", "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_TEMP_INDEX", "SQLITE_CREATE_TEMP_TABLE", "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW", "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_VIEW", "SQLITE_DROP_INDEX",
        "SQLITE_DROP_TABLE", "SQLITE_DROP_TEMP_INDEX", "SQLITE_DROP_TEMP_TABLE", "SQLITE_DROP_TEMP_TRIGGER",
        "SQLITE_DROP_TEMP_VIEW", "SQLITE_DROP_TRIGGER", "SQLITE_DROP_VIEW", "SQLITE_ALTER_TABLE",
        "SQLITE_REINDEX", "SQLITE_ANALYZE", "SQLITE_ATTACH", "SQLITE_DETACH", "SQLITE_PRAGMA",
        "SQLITE_TRANSACTION", "SQLITE_SAVEPOINT", "SQLITE_CREATE_VTABLE", "SQLITE_DROP_VTABLE", "SQLITE_COPY",
    )
    if hasattr(sqlite3, name)
}


class ToolError(ValueError):
    pass


def _database_path() -> Path:
    return default_database_path().expanduser().resolve()


def _open_readonly() -> sqlite3.Connection | None:
    path = _database_path()
    if not path.is_file():
        return None
    uri = path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    if hasattr(connection, "setlimit"):
        length_limit = getattr(sqlite3, "SQLITE_LIMIT_LENGTH", None)
        sql_limit = getattr(sqlite3, "SQLITE_LIMIT_SQL_LENGTH", None)
        column_limit = getattr(sqlite3, "SQLITE_LIMIT_COLUMN", None)
        if length_limit is not None:
            connection.setlimit(length_limit, MAX_RESULT_BYTES * 2)
        if sql_limit is not None:
            connection.setlimit(sql_limit, MAX_QUERY_LENGTH)
        if column_limit is not None:
            connection.setlimit(column_limit, 500)
    return connection


def _authorizer(action: int, arg1: str | None, arg2: str | None, _database: str | None, _trigger: str | None) -> int:
    if action in _DENIED_SQLITE_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == getattr(sqlite3, "SQLITE_FUNCTION", -1):
        function_name = (arg2 or arg1 or "").casefold()
        if function_name in {"load_extension", "writefile", "readfile"}:
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _query(connection: sqlite3.Connection, sql: str, limit: int) -> dict[str, Any]:
    if not isinstance(sql, str) or not sql.strip():
        raise ToolError("sql must be a non-empty string")
    if len(sql) > MAX_QUERY_LENGTH:
        raise ToolError(f"sql exceeds the {MAX_QUERY_LENGTH}-character limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ToolError("limit must be an integer from 1 to 500")
    connection.set_authorizer(_authorizer)
    deadline = time.monotonic() + QUERY_TIME_LIMIT_SECONDS
    connection.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
    cursor = connection.execute(sql)
    if cursor.description is None:
        raise ToolError("Only read-only SELECT queries are supported")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchmany(limit + 1)
    truncated = len(rows) > limit
    converted = [[_json_value(value) for value in tuple(row)] for row in rows[:limit]]
    result = {"columns": columns, "rows": converted, "truncated": truncated}
    while len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_RESULT_BYTES:
        if not converted:
            raise ToolError("A single result row exceeds the MCP response size limit")
        converted.pop()
        truncated = True
        result["rows"] = converted
        result["truncated"] = truncated
    if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_RESULT_BYTES:
        raise ToolError("A single result row exceeds the MCP response size limit")
    return result


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _list_tables(connection: sqlite3.Connection, dataset_id: str | None = None) -> dict[str, Any]:
    has_metadata = _has_table(connection, "_baseball_mcp_tables")
    metadata: dict[str, sqlite3.Row] = {}
    if has_metadata:
        for row in connection.execute("SELECT * FROM _baseball_mcp_tables"):
            metadata[row["table_name"]] = row
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_baseball_mcp_%' ORDER BY name"
    ).fetchall()
    tables = []
    for row in rows:
        name = row["name"]
        info = metadata.get(name)
        if dataset_id is not None and (info is None or info["dataset_id"] != dataset_id):
            continue
        tables.append(
            {
                "table_name": name,
                "dataset_id": info["dataset_id"] if info else None,
                "source_table": info["source_table"] if info else None,
                "row_count": info["row_count"] if info else None,
            }
        )
    return {"tables": tables}


def _describe_table(connection: sqlite3.Connection, name: str) -> dict[str, Any]:
    if not isinstance(name, str) or not name or not _has_table(connection, name):
        raise ToolError(f"Unknown table: {name}")
    table_info = connection.execute(f"PRAGMA table_info({quote_identifier(name)})").fetchall()
    columns = [{"name": row["name"], "type": row["type"], "nullable": not bool(row["notnull"]), "primary_key": bool(row["pk"])} for row in table_info]
    result: dict[str, Any] = {"table_name": name, "columns": columns}
    if _has_table(connection, "_baseball_mcp_tables"):
        row = connection.execute(
            "SELECT dataset_id, source_table, columns_json, row_count FROM _baseball_mcp_tables WHERE table_name = ?",
            (name,),
        ).fetchone()
        if row:
            result.update(
                {
                    "dataset_id": row["dataset_id"],
                    "source_table": row["source_table"],
                    "source_columns": json.loads(row["columns_json"]),
                    "row_count": row["row_count"],
                }
            )
    return result


def _read_database_data(kind: str, params: dict[str, Any]) -> Any:
    connection = _open_readonly()
    try:
        if kind == "datasets":
            return catalog_with_install_state(connection)
        if kind == "tables":
            return {"tables": []} if connection is None else _list_tables(connection, params.get("dataset_id"))
        if kind == "schema":
            if connection is None:
                return {"tables": []}
            tables = _list_tables(connection)["tables"]
            return {"tables": [_describe_table(connection, table["table_name"]) for table in tables]}
        if connection is None:
            raise ToolError("Baseball database not found; import a dataset and set BASEBALL_MCP_DB if it is outside the default location")
        if kind == "describe_table":
            return _describe_table(connection, params.get("table_name"))
        if kind == "query_sql":
            return _query(connection, params.get("sql"), params.get("limit", 100))
        raise ToolError(f"Unknown operation: {kind}")
    finally:
        if connection is not None:
            connection.close()


def _call_tool(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        arguments = {}
    try:
        if name == "list_datasets":
            result = _read_database_data("datasets", arguments)
        elif name == "list_tables":
            dataset_id = arguments.get("dataset_id")
            if dataset_id is not None and not isinstance(dataset_id, str):
                raise ToolError("dataset_id must be a string")
            result = _read_database_data("tables", arguments)
        elif name == "describe_table":
            result = _read_database_data("describe_table", arguments)
        elif name == "query_sql":
            result = _read_database_data("query_sql", arguments)
        else:
            raise ToolError(f"Unknown tool: {name}")
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}
    except (ToolError, sqlite3.Error, OSError, ValueError) as error:
        return {"content": [{"type": "text", "text": str(error)}], "isError": True}


def _resource(uri: str) -> dict[str, Any]:
    if uri == "baseball://datasets":
        data = _read_database_data("datasets", {})
    elif uri == "baseball://tables":
        data = _read_database_data("tables", {})
    elif uri == "baseball://schema":
        data = _read_database_data("schema", {})
    else:
        raise ToolError(f"Unknown resource: {uri}")
    return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(data, ensure_ascii=False)}]}


def _dispatch(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "Invalid Request"}}
    request_id = message.get("id")
    method = message["method"]
    params = message.get("params", {})
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Invalid params"}}
    is_notification = "id" not in message
    if method.startswith("notifications/"):
        return None
    try:
        if method == "initialize":
            requested_version = params.get("protocolVersion")
            if requested_version not in SUPPORTED_PROTOCOLS:
                raise ToolError(f"Unsupported MCP protocol version: {requested_version}")
            result = {
                "protocolVersion": requested_version,
                "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}},
                "serverInfo": {"name": "baseball-sabermetrics-mcp", "version": __version__},
                "instructions": "Use list_datasets and list_tables to discover imported sources and tables. query_sql is read-only. Data files are imported separately with the baseball-sabermetrics CLI.",
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = _call_tool(params.get("name"), params.get("arguments", {}))
        elif method == "resources/list":
            result = {"resources": RESOURCES}
        elif method == "resources/read":
            result = _resource(params.get("uri", ""))
        elif method == "shutdown":
            result = {}
        else:
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except ToolError as error:
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(error)}}
        if method == "resources/read":
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(error)}}
        if method == "tools/call":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": str(error)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(error)}}
    except (sqlite3.Error, OSError, ValueError) as error:
        if method == "tools/call":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": str(error)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": str(error)}}


def main() -> int:
    for raw_line in sys.stdin.buffer:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = _dispatch(message)
        except json.JSONDecodeError as error:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error", "data": error.msg}}
        except Exception as error:
            print(f"Unhandled server error: {error}", file=sys.stderr, flush=True)
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Internal error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
