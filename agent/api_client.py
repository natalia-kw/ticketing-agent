"""HTTP client for the ticket API, used by the agent tools and the MCP server.

Every call returns an ApiResult instead of raising, so 4xx errors can be
passed to the model as information rather than crashing the agent.
"""

import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "http://localhost:8000"


@dataclass
class ApiResult:
    ok: bool
    status_code: int | None
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """The form the model receives as a tool result."""
        if self.ok:
            return {"ok": True, "status_code": self.status_code, "data": self.data}
        return {"ok": False, "status_code": self.status_code, "error": self.error}


class TicketApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        if http_client is None:
            url = base_url or os.getenv("TICKET_API_URL", DEFAULT_BASE_URL)
            http_client = httpx.Client(base_url=url.rstrip("/"), timeout=timeout)
        self._http = http_client
        self.base_url = str(http_client.base_url).rstrip("/")

    def list_tickets(
        self, status: str | None = None, q: str | None = None
    ) -> ApiResult:
        params = {
            key: value for key, value in {"status": status, "q": q}.items() if value
        }
        return self._request("GET", "/tickets", params=params)

    def get_ticket(self, ticket_id: int) -> ApiResult:
        return self._request("GET", f"/tickets/{ticket_id}")

    def create_ticket(self, title: str, description: str = "") -> ApiResult:
        return self._request(
            "POST", "/tickets", json={"title": title, "description": description}
        )

    def update_ticket(
        self,
        ticket_id: int,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        resolution: str | None = None,
    ) -> ApiResult:
        changes = {
            "title": title,
            "description": description,
            "status": status,
            "resolution": resolution,
        }
        body = {key: value for key, value in changes.items() if value is not None}
        return self._request("PATCH", f"/tickets/{ticket_id}", json=body)

    def delete_ticket(self, ticket_id: int) -> ApiResult:
        return self._request("DELETE", f"/tickets/{ticket_id}")

    def add_comment(self, ticket_id: int, text: str) -> ApiResult:
        return self._request(
            "POST", f"/tickets/{ticket_id}/comments", json={"text": text}
        )

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> ApiResult:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.RequestError:
            return ApiResult(
                ok=False,
                status_code=None,
                error=(
                    f"Could not reach the ticket API at {self.base_url}. "
                    "Make sure it is running (uvicorn api.main:app)."
                ),
            )

        if response.is_success:
            data = response.json() if response.content else None
            return ApiResult(ok=True, status_code=response.status_code, data=data)
        return ApiResult(
            ok=False, status_code=response.status_code, error=_error_detail(response)
        )


def _error_detail(response: httpx.Response) -> str:
    """Take the API's 'detail' message, falling back to the raw response."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    return response.text or response.reason_phrase
