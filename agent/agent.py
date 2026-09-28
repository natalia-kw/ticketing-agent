"""The agent loop: sends the conversation to the model and runs requested tools."""

import json
from collections.abc import Callable
from typing import Any, Protocol

from openai import AzureOpenAI

from agent.prompts import SYSTEM_PROMPT

MAX_TOOL_ROUNDS = 8


class ToolRunner(Protocol):
    """Anything that provides tool definitions and can run tool calls."""

    definitions: list[dict[str, Any]]

    def run(self, name: str, arguments_json: str) -> dict[str, Any]: ...


class TicketAgent:
    def __init__(
        self,
        client: AzureOpenAI,
        model: str,
        tools: ToolRunner,
        on_tool_call: Callable[[str, str], None] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._tools = tools
        self._on_tool_call = on_tool_call
        self.reset()

    def reset(self) -> None:
        """Start a new conversation."""
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def ask(self, user_message: str) -> str:
        """Handle one user message and return the agent's reply."""
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": user_message})
        try:
            return self._run_until_reply()
        except Exception:
            # Keep the history valid if the model call fails halfway.
            del self.messages[checkpoint:]
            raise

    def _run_until_reply(self) -> str:
        for _ in range(MAX_TOOL_ROUNDS):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=self.messages,
                tools=self._tools.definitions,
                # This model only supports function tools on Chat Completions
                # with reasoning turned off.
                reasoning_effort="none",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                reply = message.content or ""
                self.messages.append({"role": "assistant", "content": reply})
                return reply

            self.messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in message.tool_calls
                    ],
                }
            )
            for call in message.tool_calls:
                if self._on_tool_call:
                    self._on_tool_call(call.function.name, call.function.arguments)
                result = self._tools.run(call.function.name, call.function.arguments)
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result),
                    }
                )

        return (
            "I stopped because this request needed too many steps. "
            "Please rephrase it or split it into smaller requests."
        )