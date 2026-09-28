"""In-memory ticket storage and business rules.

The API endpoints only talk to TicketRepository, never to the dictionary
directly. Moving to a real database later means replacing this one class.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from api.models import (
    Comment,
    CommentCreate,
    Ticket,
    TicketCreate,
    TicketStatus,
    TicketUpdate,
)

SEED_FILE = Path(__file__).parent / "seed_data.json"


class TicketNotFoundError(Exception):
    """Raised when no ticket exists with the requested ID."""

    def __init__(self, ticket_id: int) -> None:
        super().__init__(f"Ticket {ticket_id} not found.")
        self.ticket_id = ticket_id


class BusinessRuleError(Exception):
    """Raised when a request is well formed but breaks a business rule."""


def _now() -> datetime:
    return datetime.now(UTC)


class TicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[int, Ticket] = {}
        self._next_id = 1

    def load_seed(self, path: Path = SEED_FILE) -> None:
        """Fill the store with the example tickets from the seed file."""
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            ticket = Ticket(id=self._next_id, updated_at=item["created"], **item)
            self._save(ticket)

    def list_tickets(
        self, status: TicketStatus | None = None, q: str | None = None
    ) -> list[Ticket]:
        """Return all tickets, optionally filtered by status and/or keyword."""
        tickets = list(self._tickets.values())
        if status is not None:
            tickets = [t for t in tickets if t.status == status]
        if q:
            needle = q.lower()
            tickets = [
                t
                for t in tickets
                if needle in t.title.lower() or needle in t.description.lower()
            ]
        return tickets

    def get(self, ticket_id: int) -> Ticket:
        try:
            return self._tickets[ticket_id]
        except KeyError:
            raise TicketNotFoundError(ticket_id) from None

    def create(self, data: TicketCreate) -> Ticket:
        now = _now()
        ticket = Ticket(
            id=self._next_id,
            title=data.title,
            description=data.description,
            created=now,
            updated_at=now,
            status=TicketStatus.OPEN,
        )
        return self._save(ticket)

    def update(self, ticket_id: int, changes: TicketUpdate) -> Ticket:
        ticket = self.get(ticket_id)
        # Only apply the fields the client actually sent.
        fields = changes.model_dump(exclude_unset=True, exclude_none=True)

        if fields.get("status") == TicketStatus.RESOLVED:
            resolution = fields.get("resolution", "")
            if not resolution.strip():
                raise BusinessRuleError(
                    "A resolution note is required when setting status to RESOLVED. "
                    "Provide the 'resolution' field describing how the issue was fixed."
                )

        updated = ticket.model_copy(update={**fields, "updated_at": _now()})
        self._tickets[ticket_id] = updated
        return updated

    def delete(self, ticket_id: int) -> None:
        self.get(ticket_id)  # raises TicketNotFoundError if missing
        del self._tickets[ticket_id]

    def add_comment(self, ticket_id: int, data: CommentCreate) -> Ticket:
        ticket = self.get(ticket_id)
        now = _now()
        comment = Comment(text=data.text, created=now)
        updated = ticket.model_copy(
            update={"comments": [*ticket.comments, comment], "updated_at": now}
        )
        self._tickets[ticket_id] = updated
        return updated

    def _save(self, ticket: Ticket) -> Ticket:
        """Store a new ticket and move the ID counter forward."""
        self._tickets[ticket.id] = ticket
        self._next_id += 1
        return ticket