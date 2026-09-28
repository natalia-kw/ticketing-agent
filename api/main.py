"""FastAPI application: HTTP endpoints and error handling for the ticket API."""

import os
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.models import CommentCreate, Ticket, TicketCreate, TicketStatus, TicketUpdate
from api.repository import BusinessRuleError, TicketNotFoundError, TicketRepository

load_dotenv()

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_repository(request: Request) -> TicketRepository:
    return request.app.state.repository


Repo = Annotated[TicketRepository, Depends(get_repository)]


# ---------- Endpoints ----------


@router.get("")
def list_tickets(
    repo: Repo,
    status: Annotated[
        TicketStatus | None, Query(description="Only tickets with this status")
    ] = None,
    q: Annotated[
        str | None, Query(description="Keyword to search in title and description")
    ] = None,
) -> list[Ticket]:
    """List tickets. Both filters are optional and can be combined."""
    return repo.list_tickets(status=status, q=q)


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, repo: Repo) -> Ticket:
    """Get a single ticket by ID."""
    return repo.get(ticket_id)


@router.post("", status_code=201)
def create_ticket(data: TicketCreate, repo: Repo) -> Ticket:
    """Create a new ticket. It always starts with status OPEN."""
    return repo.create(data)


@router.patch("/{ticket_id}")
def update_ticket(ticket_id: int, changes: TicketUpdate, repo: Repo) -> Ticket:
    """Update only the fields that are sent.

    Setting status to RESOLVED requires a resolution note.
    """
    return repo.update(ticket_id, changes)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int, repo: Repo) -> None:
    """Delete a ticket."""
    repo.delete(ticket_id)


@router.post("/{ticket_id}/comments", status_code=201)
def add_comment(ticket_id: int, data: CommentCreate, repo: Repo) -> Ticket:
    """Add a comment to a ticket and return the updated ticket."""
    return repo.add_comment(ticket_id, data)


# ---------- Error handling ----------


def _describe_validation_error(error: dict[str, Any]) -> str:
    """Turn one Pydantic validation error into a readable sentence."""
    field = ".".join(
        str(part) for part in error["loc"] if part not in ("body", "query", "path")
    )
    kind = error["type"]

    if kind == "enum":
        valid = ", ".join(s.value for s in TicketStatus)
        return f"Invalid status '{error.get('input')}'. Valid values are: {valid}."
    if kind == "extra_forbidden":
        return f"Unknown field '{field}' is not allowed."
    if kind == "missing":
        return (
            f"Missing required field '{field}'."
            if field
            else "Request body is missing."
        )
    return f"Invalid value for '{field or 'request'}': {error['msg']}."


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = [_describe_validation_error(e) for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": " ".join(messages)})


async def handle_not_found(request: Request, exc: TicketNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def handle_business_rule(
    request: Request, exc: BusinessRuleError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ---------- App setup ----------


def create_app(seed: bool | None = None) -> FastAPI:
    """Build the app. If seed is not given, it is read from SEED_DATA in .env."""
    if seed is None:
        seed = os.getenv("SEED_DATA", "true").strip().lower() == "true"

    app = FastAPI(
        title="Mock Ticketing API",
        version="1.0.0",
        description="A simple in-memory support ticketing API.",
    )

    repository = TicketRepository()
    if seed:
        repository.load_seed()
    app.state.repository = repository

    app.include_router(router)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(TicketNotFoundError, handle_not_found)
    app.add_exception_handler(BusinessRuleError, handle_business_rule)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
