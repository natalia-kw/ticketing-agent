"""Command-line chat with the ticket agent.

Usage:
    python -m agent.cli           call the API directly, show tool calls
    python -m agent.cli --mcp     get tools from the MCP server instead
    python -m agent.cli --quiet   hide tool calls
"""

import argparse
import sys

from openai import OpenAIError

from agent.agent import TicketAgent
from agent.api_client import TicketApiClient
from agent.llm import ConfigError, create_client
from agent.mcp_tools import McpToolRunner, default_server_params
from agent.tools import ToolExecutor

EXIT_COMMANDS = {"exit", "quit"}


def print_tool_call(name: str, arguments: str) -> None:
    print(f"  [tool] {name}({arguments})")


def chat(agent: TicketAgent) -> None:
    print("Ticket assistant ready. Type 'reset' to start over or 'exit' to quit.")
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not user_input:
            continue
        if user_input.lower() in EXIT_COMMANDS:
            return
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with the ticket agent.")
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Get tools from the MCP server instead of calling the API directly.",
    )
    parser.add_argument("--quiet", action="store_true", help="Hide tool calls.")
    args = parser.parse_args()

    try:
        client, model = create_client()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1

    tools: ToolExecutor | McpToolRunner
    if args.mcp:
        try:
            tools = McpToolRunner(default_server_params())
        except Exception as exc:
            print(f"Could not start the MCP server: {exc}")
            return 1
        print("Tools are provided by the MCP server.")
    else:
        tools = ToolExecutor(TicketApiClient())

    agent = TicketAgent(
        client,
        model,
        tools,
        on_tool_call=None if args.quiet else print_tool_call,
    )
    try:
        chat(agent)
    finally:
        tools.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
