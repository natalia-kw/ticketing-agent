"""Tests for the agent's API client, run against the real app in memory."""

import pytest
from fastapi.testclient import TestClient

from agent.api_client import TicketApiClient
from api.main import create_app


@pytest.fixture
def api() -> TicketApiClient:
    return TicketApiClient(http_client=TestClient(create_app(seed=True)))


def test_success_returns_data(api):
    result = api.get_ticket(3)
    assert result.ok
    assert result.data["title"] == "Cannot access shared drive"


def test_not_found_returns_api_message(api):
    result = api.get_ticket(999)
    assert not result.ok
    assert result.status_code == 404
    assert result.error == "Ticket 999 not found."


def test_invalid_status_returns_valid_options(api):
    result = api.update_ticket(1, status="PROGRESS")
    assert result.status_code == 422
    assert "OPEN, RESOLVED, CLOSED" in result.error


def test_update_sends_only_given_fields(api):
    result = api.update_ticket(1, status="RESOLVED", resolution="Replaced faulty cable")
    assert result.ok
    assert result.data["resolution"] == "Replaced faulty cable"


def test_delete_returns_no_data(api):
    result = api.delete_ticket(1)
    assert result.ok
    assert result.data is None


def test_unreachable_api_gives_helpful_error():
    api = TicketApiClient(base_url="http://127.0.0.1:1")
    result = api.list_tickets()
    assert not result.ok
    assert result.status_code is None
    assert "Could not reach the ticket API" in result.error
