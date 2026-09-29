"""Tool runner that gets its tools from the MCP server instead of calling the API.

The MCP client is asynchronous, while the agent loop is synchronous. The runner
keeps one MCP connection open on an event loop in a background thread for the
whole session, and the agent calls run() like any other tool runner.
"""

import asyncio
import json
import os
import re
import sys
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters
from mcp.types import TextContent

from agent.api_client import DEFAULT_BASE_URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 60


def default_server_params() -> StdioServerParameters:
    """How to start the MCP server as a subprocess.

    The subprocess does not inherit our environment, so the settings it needs
    are passed explicitly.
    """
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env={
            "PYTHONPATH": str(PROJECT_ROOT),
            "TICKET_API_URL": os.getenv("TICKET_API_URL", DEFAULT_BASE_URL),
        },
    )


def convert_result(result: Any) -> dict[str, Any]:
    """Turn an MCP tool result into the same format the direct tools return."""
    text = "\n".join(
        block.text for block in result.content if isinstance(block, TextContent)
    )
    if result.is_error:
        match = re.search(r"HTTP (\d{3}): (.*)", text, re.DOTALL)
        if match:
            return {
                "ok": False,
                "status_code": int(match.group(1)),
                "error": match.group(2).strip(),
            }
        return {"ok": False, "status_code": None, "error": text}

    data = result.structured_content
    # Tools returning a list are wrapped by the SDK as {"result": [...]}.
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    return {"ok": True, "data": data}


class McpToolRunner:
    def __init__(self, params: StdioServerParameters) -> None:
        self._client: Client | None = None
        self._stop = asyncio.Event()
        self._connected: Future[None] = Future()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

        self._session = asyncio.run_coroutine_threadsafe(
            self._hold_connection(params), self._loop
        )
        self._connected.result(timeout=TIMEOUT_SECONDS)
        self.definitions = self._call(self._load_definitions())

    def run(self, name: str, arguments_json: str) -> dict[str, Any]:
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            return {
                "ok": False,
                "status_code": None,
                "error": f"Arguments for '{name}' were not valid JSON.",
            }
        result = self._call(self._client.call_tool(name, arguments))
        return convert_result(result)

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._stop.set)
        try:
            self._session.result(timeout=10)
        except Exception:
            pass  # The session is shutting down anyway.
        self._loop.call_soon_threadsafe(self._loop.stop)

    async def _hold_connection(self, params: StdioServerParameters) -> None:
        """Open the MCP connection and keep it open until close() is called."""
        try:
            async with Client(params) as client:
                self._client = client
                self._connected.set_result(None)
                await self._stop.wait()
        except Exception as exc:
            if not self._connected.done():
                self._connected.set_exception(exc)
            raise

    async def _load_definitions(self) -> list[dict[str, Any]]:
        """Convert the server's tool list into the format the model expects."""
        listed = await self._client.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in listed.tools
        ]

    def _call(self, coroutine: Any) -> Any:
        """Run a coroutine on the background loop and wait for its result."""
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result(timeout=TIMEOUT_SECONDS)
