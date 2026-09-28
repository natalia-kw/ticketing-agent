"""Agent tests with a scripted fake model and the real API running in memory."""

import copy
import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from agent.agent import MAX_TOOL_ROUNDS, TicketAgent
from agent.api_client import TicketApiClient
from agent.tools import ToolExecutor
from api.main import create_app

# ---------- Helpers that imitate the OpenAI client ----------


def tool_call(call_id: str, name: str, arguments: dict) -> NS:
    return NS(
        id=call_id,
        type="function",
        function=NS(name=name, arguments=json.dumps(arguments)),
    )


def model_reply(content: str | None = None, tool_calls: list | None = None) -> NS:
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


class FakeModel:
    """Returns scripted responses and records every request it receives."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.requests: list[list[dict]] = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs["messages"]))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def last_tool_result(model: FakeModel) -> dict:
    """The most recent tool result the agent sent to the model."""
    tool_messages = [m for m in model.requests[-1] if m["role"] == "tool"]
    return json.loads(tool_messages[-1]["content"])


@pytest.fixture
def api() -> TicketApiClient:
    return TicketApiClient(http_client=TestClient(create_app(seed=True)))


def make_agent(model: FakeModel, api: TicketApiClient) -> TicketAgent:
    return TicketAgent(model, "fake-model", ToolExecutor(api))


# ---------- Error handling ----------


def test_invalid_status_error_reaches_the_model(api):
    model = FakeModel(
        [
            model_reply(
                tool_calls=[
                    tool_call(
                        "1", "update_ticket", {"ticket_id": 1, "status": "PROGRESS"}
                    )
                ]
            ),
            model_reply("PROGRESS is not valid. Use OPEN, RESOLVED or CLOSED."),
        ]
    )
    reply = make_agent(model, api).ask("Set ticket 1 to PROGRESS")

    result = last_tool_result(model)
    assert result["ok"] is False
    assert result["status_code"] == 422
    assert "OPEN, RESOLVED, CLOSED" in result["error"]
    assert reply == "PROGRESS is not valid. Use OPEN, RESOLVED or CLOSED."


def test_missing_ticket_error_reaches_the_model(api):
    model = FakeModel(
        [
            model_reply(
                tool_calls=[
                    tool_call(
                        "1", "update_ticket", {"ticket_id": 999, "status": "CLOSED"}
                    )
                ]
            ),
            model_reply("Ticket 999 does not exist."),
        ]
    )
    make_agent(model, api).ask("Close ticket 999")

    result = last_tool_result(model)
    assert result["status_code"] == 404
    assert result["error"] == "Ticket 999 not found."


# ---------- Orchestration ----------


def test_chains_search_and_update(api):
    model = FakeModel(
        [
            model_reply(tool_calls=[tool_call("1", "list_tickets", {"q": "printer"})]),
            model_reply(
                tool_calls=[
                    tool_call(
                        "2", "update_ticket", {"ticket_id": 2, "status": "CLOSED"}
                    )
                ]
            ),
            model_reply("Closed #2."),
        ]
    )
    reply = make_agent(model, api).ask("Close the printer ticket")

    assert reply == "Closed #2."
    assert api.get_ticket(2).data["status"] == "CLOSED"


def test_conversation_history_is_kept_between_messages(api):
    model = FakeModel([model_reply("First answer."), model_reply("Second answer.")])
    agent = make_agent(model, api)
    agent.ask("First question")
    agent.ask("Second question")

    contents = [m["content"] for m in model.requests[-1]]
    assert "First question" in contents
    assert "First answer." in contents


# ---------- Safety limits ----------


def test_stops_after_too_many_tool_rounds(api):
    endless = [
        model_reply(tool_calls=[tool_call(str(i), "list_tickets", {})])
        for i in range(MAX_TOOL_ROUNDS)
    ]
    reply = make_agent(FakeModel(endless), api).ask("Loop forever")
    assert "too many steps" in reply


def test_history_is_rolled_back_when_model_call_fails(api):
    model = FakeModel([RuntimeError("Azure is down")])
    agent = make_agent(model, api)
    before = list(agent.messages)

    with pytest.raises(RuntimeError):
        agent.ask("Hello")
    assert agent.messages == before


# ---------- Tool executor ----------


def test_executor_reports_unknown_tool(api):
    result = ToolExecutor(api).run("reboot_server", "{}")
    assert result["ok"] is False
    assert "Unknown tool" in result["error"]


def test_executor_reports_wrong_arguments(api):
    result = ToolExecutor(api).run("get_ticket", '{"id": 1}')
    assert result["ok"] is False
    assert "Invalid arguments" in result["error"]


def test_executor_reports_invalid_json(api):
    result = ToolExecutor(api).run("get_ticket", "{not json")
    assert result["ok"] is False
    assert "not valid JSON" in result["error"]
