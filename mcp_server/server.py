"""MCP server exposing the ticket API as tools, built with the official MCP SDK.

The agent starts it automatically with:  python -m agent.cli --mcp
It can also be added to any MCP host (for example Claude Desktop) with the
command:  python -m mcp_server.server
"""

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from agent.api_client import ApiResult, TicketApiClient

mcp = MCPServer(
    "ticketing",
    instructions="Tools for managing support tickets in the mock ticketing API.",
)
api = TicketApiClient()


def _unwrap(result: ApiResult) -> Any:
    """Return the data on success, or raise a ToolError with the API's message."""
    if result.ok:
        return result.data
    if result.status_code is None:
        raise ToolError(result.error)
    raise ToolError(f"HTTP {result.status_code}: {result.error}")


@mcp.tool()
def list_tickets(
    status: str | None = None, q: str | None = None
) -> list[dict[str, Any]]:
    """List tickets. Optionally filter by status and/or a keyword found in the
    title or description. Use the keyword search to find a ticket the user
    describes in words instead of by ID."""
    return _unwrap(api.list_tickets(status=status, q=q))


@mcp.tool()
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Get the full details of one ticket, including comments."""
    return _unwrap(api.get_ticket(ticket_id))


@mcp.tool()
def create_ticket(title: str, description: str = "") -> dict[str, Any]:
    """Create a new ticket. New tickets always start with status OPEN."""
    return _unwrap(api.create_ticket(title, description))


@mcp.tool()
def update_ticket(
    ticket_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    resolution: str | None = None,
) -> dict[str, Any]:
    """Update a ticket. Only the fields that are given are changed. Pass the
    status exactly as the user requested it, the API validates it. A resolution
    is required when setting status to RESOLVED."""
    return _unwrap(
        api.update_ticket(
            ticket_id,
            title=title,
            description=description,
            status=status,
            resolution=resolution,
        )
    )


@mcp.tool()
def delete_ticket(ticket_id: int) -> dict[str, Any]:
    """Permanently delete a ticket. Only call this after the user has
    explicitly confirmed the deletion."""
    _unwrap(api.delete_ticket(ticket_id))
    return {"deleted": ticket_id}


@mcp.tool()
def add_comment(ticket_id: int, text: str) -> dict[str, Any]:
    """Add a comment to a ticket."""
    return _unwrap(api.add_comment(ticket_id, text))


if __name__ == "__main__":
    mcp.run()
