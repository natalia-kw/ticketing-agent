"""Data models for the ticketing API.

These classes describe what a ticket looks like and what clients may send.
FastAPI uses them to validate every request automatically.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Comment(BaseModel):
    text: str
    created: datetime


class Ticket(BaseModel):
    """A ticket as stored and returned by the API."""

    id: int
    title: str
    description: str
    created: datetime
    updated_at: datetime
    status: TicketStatus
    resolution: str | None = None
    comments: list[Comment] = Field(default_factory=list)


class TicketCreate(BaseModel):
    """Body for creating a ticket. New tickets always start as OPEN."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class TicketUpdate(BaseModel):
    """Body for a partial update. Only the fields that are sent get changed."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TicketStatus | None = None
    resolution: str | None = Field(default=None, max_length=2000)


class CommentCreate(BaseModel):
    """Body for adding a comment to a ticket."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class ErrorResponse(BaseModel):
    """The body of every error response."""

    detail: str = Field(examples=["Ticket 999 not found."])
