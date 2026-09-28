"""Tools the model can call, and the code that runs them."""

import json
from collections.abc import Callable
from typing import Any

from agent.api_client import ApiResult, TicketApiClient


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TICKET_ID = {"type": "integer", "description": "The numeric ID of the ticket."}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    _tool(
        "list_tickets",
        "List tickets. Optionally filter by status and/or a keyword found in the "
        "title or description. Use the keyword search to find a ticket the user "
        "describes in words instead of by ID.",
        {
            "status": {
                "type": "string",
                "description": "Only return tickets with this status.",
            },
            "q": {
                "type": "string",
                "description": "Keyword to search for in title and description.",
            },
        },
        [],
    ),
    _tool(
        "get_ticket",
        "Get the full details of one ticket, including comments.",
        {"ticket_id": TICKET_ID},
        ["ticket_id"],
    ),
    _tool(
        "create_ticket",
        "Create a new ticket. New tickets always start with status OPEN.",
        {
            "title": {"type": "string", "description": "Short summary of the issue."},
            "description": {
                "type": "string",
                "description": "More detail about the issue.",
            },
        },
        ["title"],
    ),
    _tool(
        "update_ticket",
        "Update a ticket. Only the fields that are given are changed.",
        {
            "ticket_id": TICKET_ID,
            "title": {"type": "string", "description": "New title."},
            "description": {"type": "string", "description": "New description."},
            "status": {
                "type": "string",
                "description": "New status, exactly as the user requested it. "
                "The API validates it.",
            },
            "resolution": {
                "type": "string",
                "description": "How the issue was fixed. The API requires this "
                "when setting status to RESOLVED.",
            },
        },
        ["ticket_id"],
    ),
    _tool(
        "delete_ticket",
        "Permanently delete a ticket. Only call this after the user has "
        "explicitly confirmed the deletion.",
        {"ticket_id": TICKET_ID},
        ["ticket_id"],
    ),
    _tool(
        "add_comment",
        "Add a comment to a ticket.",
        {
            "ticket_id": TICKET_ID,
            "text": {"type": "string", "description": "The comment text."},
        },
        ["ticket_id", "text"],
    ),
]


class ToolExecutor:
    """Runs tool calls from the model against the ticket API."""

    definitions = TOOL_DEFINITIONS

    def __init__(self, api: TicketApiClient) -> None:
        self._handlers: dict[str, Callable[..., ApiResult]] = {
            "list_tickets": api.list_tickets,
            "get_ticket": api.get_ticket,
            "create_ticket": api.create_ticket,
            "update_ticket": api.update_ticket,
            "delete_ticket": api.delete_ticket,
            "add_comment": api.add_comment,
        }

    def run(self, name: str, arguments_json: str) -> dict[str, Any]:
        """Run one tool call and return a result the model can read."""
        handler = self._handlers.get(name)
        if handler is None:
            return _tool_error(f"Unknown tool '{name}'.")
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            return _tool_error(f"Arguments for '{name}' were not valid JSON.")
        try:
            return handler(**arguments).to_dict()
        except TypeError as exc:
            return _tool_error(f"Invalid arguments for '{name}': {exc}")


def _tool_error(message: str) -> dict[str, Any]:
    return {"ok": False, "status_code": None, "error": message}
