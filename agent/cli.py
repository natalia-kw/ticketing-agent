"""Command-line chat with the ticket agent.

Usage:
    python -m agent.cli           show tool calls as they happen
    python -m agent.cli --quiet   hide tool calls
"""

import argparse
import sys

from openai import OpenAIError

from agent.agent import TicketAgent
from agent.api_client import TicketApiClient
from agent.llm import ConfigError, create_client
from agent.tools import ToolExecutor

EXIT_COMMANDS = {"exit", "quit"}


def print_tool_call(name: str, arguments: str) -> None:
    print(f"  [tool] {name}({arguments})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with the ticket agent.")
    parser.add_argument("--quiet", action="store_true", help="Hide tool calls.")
    args = parser.parse_args()

    try:
        client, model = create_client()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1

    api = TicketApiClient()
    agent = TicketAgent(
        client,
        model,
        ToolExecutor(api),
        on_tool_call=None if args.quiet else print_tool_call,
    )

    print("Ticket assistant ready. Type 'reset' to start over or 'exit' to quit.")
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in EXIT_COMMANDS:
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("Conversation cleared.")
            continue

        try:
            reply = agent.ask(user_input)
        except OpenAIError as exc:
            print(f"\nAgent: The language model request failed: {exc}")
            continue
        print(f"\nAgent: {reply}")

    api.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
