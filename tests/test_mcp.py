"""Tests for the MCP server, connected in memory to the real API."""

import pytest
from fastapi.testclient import TestClient
from mcp import Client

import mcp_server.server as mcp_module
from agent.api_client import TicketApiClient
from agent.mcp_tools import convert_result
from api.main import create_app

EXPECTED_TOOLS = {
    "list_tickets",
    "get_ticket",
    "create_ticket",
    "update_ticket",
    "delete_ticket",
    "add_comment",
}


@pytest.fixture
def server(monkeypatch):
    """The MCP server, wired to a fresh in-memory API."""
    api = TicketApiClient(http_client=TestClient(create_app(seed=True)))
    monkeypatch.setattr(mcp_module, "api", api)
    return mcp_module.mcp


@pytest.mark.anyio
async def test_exposes_all_ticket_tools(server):
    async with Client(server) as client:
        listed = await client.list_tools()
    assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS


@pytest.mark.anyio
async def test_get_ticket_returns_data(server):
    async with Client(server) as client:
        result = await client.call_tool("get_ticket", {"ticket_id": 3})
    converted = convert_result(result)
    assert converted["ok"] is True
    assert converted["data"]["title"] == "Cannot access shared drive"


@pytest.mark.anyio
async def test_list_result_is_unwrapped(server):
    async with Client(server) as client:
        result = await client.call_tool("list_tickets", {"status": "OPEN"})
    converted = convert_result(result)
    assert len(converted["data"]) == 6


@pytest.mark.anyio
async def test_invalid_status_keeps_code_and_message(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "update_ticket", {"ticket_id": 1, "status": "PROGRESS"}
        )
    assert result.is_error
    converted = convert_result(result)
    assert converted["status_code"] == 422
    assert "OPEN, RESOLVED, CLOSED" in converted["error"]


@pytest.mark.anyio
async def test_missing_ticket_keeps_code_and_message(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "update_ticket", {"ticket_id": 999, "status": "CLOSED"}
        )
    converted = convert_result(result)
    assert converted["status_code"] == 404
    assert converted["error"] == "Ticket 999 not found."
