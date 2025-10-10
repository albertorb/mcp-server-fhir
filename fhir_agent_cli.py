#!/usr/bin/env python3
"""
Simple OpenAI Agent that uses the Epic FHIR MCP Server for testing.

This script demonstrates how to use the OpenAI Agents SDK with an MCP server
over the Streamable HTTP transport.

Usage:
    # Install dependencies first with uv:
    uv add openai-agents

    # For HTTP mode (requires server running on http://localhost:8000):
    # Terminal 1: Start server
    uv run python -m src.server --transport http
    # Terminal 2: Run agent
    uv run python fhir_agent_cli.py --url http://localhost:8000/mcp
"""

import asyncio
import argparse

from dotenv import load_dotenv

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp


EXIT_COMMANDS = {"exit", "quit", "q"}


load_dotenv()


def build_agent(mcp_server) -> Agent:
    """Create an agent configured for Epic FHIR assistance."""
    return Agent(
        name="FHIR Assistant",
        instructions=(
            "You are a helpful medical assistant with access to the Epic FHIR API.\n"
            "You can search for patients, retrieve demographics, medications, conditions, "
            "and other medical information. Always respect patient privacy and provide "
            "clear, accurate information."
        ),
        mcp_servers=[mcp_server],
    )


async def interactive_chat(agent: Agent, transport_label: str) -> None:
    """Run an interactive chat session with the provided agent."""
    print("Interactive FHIR Assistant (type 'exit' to quit)")
    print(f"Connected via {transport_label}\n")

    input_history = []

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except EOFError:
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in EXIT_COMMANDS:
            print("Goodbye!")
            break

        input_history.append({"role": "user", "content": user_input})

        print("Assistant: ", end="", flush=True)
        result = await Runner.run(starting_agent=agent, input=input_history)
        print(result.final_output)

        input_history = result.to_input_list()


async def run_agent_http(server_url: str = "http://localhost:8000/mcp"):
    """Run agent with Streamable HTTP transport (remote MCP server via HTTP)."""
    print(f"Connecting to Epic FHIR MCP Server at {server_url}...")
    print("Using Streamable HTTP transport\n")
    
    async with MCPServerStreamableHttp(
        name="Epic FHIR Server",
        params={
            "url": server_url,
        },
    ) as mcp_server:
        print("Connected to MCP server\n")

        agent = build_agent(mcp_server)
        await interactive_chat(agent, "Streamable HTTP")


async def main():
    parser = argparse.ArgumentParser(
        description="Test OpenAI Agent with Epic FHIR MCP Server"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/mcp",
        help="Streamable HTTP server URL"
    )
    
    args = parser.parse_args()
    
    try:
        await run_agent_http(args.url)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
