"""Tests for the ticket API, including every business error case."""

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client() -> TestClient:
    """A fresh app with seed data for every test."""
    return TestClient(create_app(seed=True))


# ---------- Reading ----------


def test_list_all_tickets(client):
    response = client.get("/tickets")
    assert response.status_code == 200
    assert len(response.json()) == 10


def test_filter_by_status(client):
    response = client.get("/tickets", params={"status": "OPEN"})
    tickets = response.json()
    assert len(tickets) == 6
    assert all(t["status"] == "OPEN" for t in tickets)


def test_search_by_keyword(client):
    tickets = client.get("/tickets", params={"q": "printer"}).json()
    assert [t["id"] for t in tickets] == [2]


def test_filters_combine(client):
    # The Wi-Fi ticket exists but is RESOLVED, so status=OPEN excludes it.
    assert client.get("/tickets", params={"q": "wi-fi"}).json()
    assert client.get("/tickets", params={"q": "wi-fi", "status": "OPEN"}).json() == []


def test_invalid_status_filter_lists_valid_values(client):
    response = client.get("/tickets", params={"status": "PROGRESS"})
    assert response.status_code == 422
    assert "OPEN, RESOLVED, CLOSED" in response.json()["detail"]


def test_get_ticket(client):
    response = client.get("/tickets/3")
    assert response.status_code == 200
    assert response.json()["title"] == "Cannot access shared drive"


def test_get_missing_ticket_returns_404(client):
    response = client.get("/tickets/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket 999 not found."


# ---------- Creating ----------


def test_create_ticket(client):
    response = client.post(
        "/tickets",
        json={"title": "Keyboard not working", "description": "Keys do not respond."},
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["id"] == 11
    assert ticket["status"] == "OPEN"
    assert ticket["resolution"] is None


def test_create_ticket_with_empty_title_fails(client):
    response = client.post("/tickets", json={"title": ""})
    assert response.status_code == 422
    assert "title" in response.json()["detail"]


def test_create_ticket_with_unknown_field_fails(client):
    response = client.post("/tickets", json={"title": "Test", "priority": "high"})
    assert response.status_code == 422
    assert "priority" in response.json()["detail"]


# ---------- Updating ----------


def test_update_with_invalid_status_lists_valid_values(client):
    response = client.patch("/tickets/1", json={"status": "PROGRESS"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "PROGRESS" in detail
    assert "OPEN, RESOLVED, CLOSED" in detail


def test_resolve_without_resolution_fails(client):
    response = client.patch("/tickets/1", json={"status": "RESOLVED"})
    assert response.status_code == 422
    assert "resolution" in response.json()["detail"].lower()


def test_resolve_with_blank_resolution_fails(client):
    response = client.patch(
        "/tickets/1", json={"status": "RESOLVED", "resolution": "   "}
    )
    assert response.status_code == 422


def test_resolve_with_resolution(client):
    response = client.patch(
        "/tickets/1",
        json={"status": "RESOLVED", "resolution": "Replaced faulty cable"},
    )
    assert response.status_code == 200
    ticket = response.json()
    assert ticket["status"] == "RESOLVED"
    assert ticket["resolution"] == "Replaced faulty cable"
    assert ticket["updated_at"] > ticket["created"]


def test_partial_update_keeps_other_fields(client):
    before = client.get("/tickets/1").json()
    after = client.patch("/tickets/1", json={"title": "New title"}).json()
    assert after["title"] == "New title"
    assert after["description"] == before["description"]
    assert after["status"] == before["status"]


def test_update_missing_ticket_returns_404(client):
    response = client.patch("/tickets/999", json={"status": "CLOSED"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket 999 not found."


# ---------- Deleting and comments ----------


def test_delete_ticket(client):
    assert client.delete("/tickets/1").status_code == 204
    assert client.get("/tickets/1").status_code == 404


def test_delete_missing_ticket_returns_404(client):
    assert client.delete("/tickets/999").status_code == 404


def test_add_comment(client):
    response = client.post("/tickets/9/comments", json={"text": "Ordered a new lamp."})
    assert response.status_code == 201
    comments = response.json()["comments"]
    assert len(comments) == 2
    assert comments[-1]["text"] == "Ordered a new lamp."


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_docs_describe_the_real_error_format(client):
    schema = client.get("/openapi.json").json()
    patch_responses = schema["paths"]["/tickets/{ticket_id}"]["patch"]["responses"]
    for code in ("404", "422"):
        ref = patch_responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse")
