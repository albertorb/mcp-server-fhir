"""Streamable HTTP MCP Server for Epic FHIR API.

This server supports both stdio and Streamable HTTP transports.
Streamable HTTP is the modern, recommended transport for production deployments.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

try:
    from .config import EpicConfig, ServerConfig, setup_logging
    from .epic_client import EpicFHIRClient
    from .tools import (
        EPIC_FHIR_TOOLS,
        format_bundle_response,
        format_patient_response,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.config import EpicConfig, ServerConfig, setup_logging
    from src.epic_client import EpicFHIRClient
    from src.tools import (
        EPIC_FHIR_TOOLS,
        format_bundle_response,
        format_patient_response,
    )

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global Epic client instance (initialized in lifespan for HTTP mode, in run_stdio for stdio mode)
epic_client: EpicFHIRClient | None = None


# Initialize MCP server (must be created before session_manager)
mcp_server = Server("epic-fhir-mcp")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available FHIR tools."""
    logger.debug(f"Listing {len(EPIC_FHIR_TOOLS)} available tools")
    return EPIC_FHIR_TOOLS


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from LLM.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of text content responses
    """
    if not epic_client:
        error_msg = "Epic FHIR client not initialized"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    logger.info(f"Tool call: {name} with arguments: {arguments}")

    try:
        text = await _execute_tool(name, arguments)
        return [TextContent(type="text", text=text)]
    except Exception as e:
        error_msg = f"Error executing tool '{name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=error_msg)]


async def _execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute specific tool logic.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Formatted response text
    """
    if name == "get_patient":
        data = await epic_client.get_patient(arguments["patient_id"])
        return format_patient_response(data)

    elif name == "search_patients":
        data = await epic_client.search_patients(**arguments)
        return format_bundle_response(data, "Patient")

    elif name == "get_patient_conditions":
        data = await epic_client.get_conditions(arguments["patient_id"])
        return format_bundle_response(data, "Condition")

    elif name == "get_patient_medications":
        data = await epic_client.get_medications(arguments["patient_id"])
        return format_bundle_response(data, "MedicationRequest")

    elif name == "get_patient_observations":
        patient_id = arguments["patient_id"]
        category = arguments.get("category")
        data = await epic_client.get_observations(patient_id, category=category)
        return format_bundle_response(data, "Observation")

    elif name == "get_patient_allergies":
        data = await epic_client.get_allergies(arguments["patient_id"])
        return format_bundle_response(data, "AllergyIntolerance")

    elif name == "get_patient_immunizations":
        data = await epic_client.get_immunizations(arguments["patient_id"])
        return format_bundle_response(data, "Immunization")

    elif name == "get_patient_procedures":
        data = await epic_client.get_procedures(arguments["patient_id"])
        return format_bundle_response(data, "Procedure")

    else:
        return f"Unknown tool: {name}"


# Create session manager for Streamable HTTP
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    json_response=False,  # Use SSE streaming for responses
    stateless=False,  # Maintain session state
)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Application lifespan manager for startup/shutdown.
    
    This combines Epic FHIR client initialization with MCP session manager lifecycle.
    """
    global epic_client

    # Startup
    logger.info("Starting Epic FHIR MCP Server...")
    try:
        # Initialize Epic FHIR client
        epic_config = EpicConfig.from_env()
        epic_client = EpicFHIRClient(
            client_id=epic_config.client_id,
            private_key_path=epic_config.private_key_path,
            token_url=epic_config.token_url,
            fhir_base_url=epic_config.fhir_base_url,
        )
        logger.info("Epic FHIR client initialized successfully")
        
        # Start MCP session manager (this must be done after epic_client is initialized)
        async with session_manager.run():
            yield
            
    except Exception as e:
        logger.error(f"Failed to initialize Epic client: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Epic FHIR MCP Server...")
        if epic_client:
            await epic_client.close()


# ASGI handler for streamable HTTP connections
async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager.handle_request(scope, receive, send)


# Create Starlette app with Streamable HTTP transport
app = Starlette(
    debug=False,
    routes=[
        Mount("/mcp", app=handle_streamable_http),
    ],
    lifespan=lifespan,  # Use the combined lifespan that initializes epic_client AND runs session_manager
)


def main():
    """Run the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Epic FHIR MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio (for Claude Desktop) or http (for Streamable HTTP)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP mode")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP mode")
    
    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio mode for Claude Desktop
        import asyncio
        
        async def run_stdio():
            """Run server with stdio transport."""
            global epic_client
            
            logger.info("Starting Epic FHIR MCP Server (stdio mode)...")
            try:
                epic_config = EpicConfig.from_env()
                epic_client = EpicFHIRClient(
                    client_id=epic_config.client_id,
                    private_key_path=epic_config.private_key_path,
                    token_url=epic_config.token_url,
                    fhir_base_url=epic_config.fhir_base_url,
                )
                logger.info("Epic FHIR client initialized successfully")
                
                async with stdio_server() as (read_stream, write_stream):
                    await mcp_server.run(
                        read_stream,
                        write_stream,
                        mcp_server.create_initialization_options(),
                    )
            except Exception as e:
                logger.error(f"Failed to start server: {e}")
                raise
            finally:
                if epic_client:
                    await epic_client.close()
        
        asyncio.run(run_stdio())
    
    else:
        # Streamable HTTP mode
        import uvicorn
        
        logger.info(f"Starting Epic FHIR MCP Server (Streamable HTTP mode) on {args.host}:{args.port}")
        logger.info(f"Server will be available at http://{args.host}:{args.port}/mcp")
        uvicorn.run(
            "src.server:app",
            host=args.host,
            port=args.port,
            log_level="info",
        )


if __name__ == "__main__":
    main()
