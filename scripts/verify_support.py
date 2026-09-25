from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def start_server(database: Path) -> "MCPProcess":
    return MCPProcess(database)


class MCPProcess:
    def __init__(self, database: Path):
        env = os.environ.copy()
        env["BASEBALL_MCP_DB"] = str(database)
        src_path = str(ROOT / "src")
        env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "baseball_mcp.server"],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._counter = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._counter += 1
        request_id = self._counter
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(f"MCP server exited before responding to {method}: {stderr}")
        response = json.loads(line)
        assert response.get("id") == request_id, response
        return response

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate(timeout=5)


def initialize(client: MCPProcess) -> dict[str, Any]:
    response = client.request(
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "verify-script", "version": "1"},
        },
    )
    assert "result" in response, response
    client.notify("notifications/initialized")
    return response["result"]


def call_tool(client: MCPProcess, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.request("tools/call", {"name": name, "arguments": arguments or {}})
    assert "result" in response, response
    return response["result"]


def content_json(result: dict[str, Any]) -> Any:
    assert result.get("content"), result
    return json.loads(result["content"][0]["text"])
