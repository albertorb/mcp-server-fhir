"""Configuration management for Epic FHIR MCP Server."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class EpicConfig:
    """Epic FHIR API configuration."""

    client_id: str
    private_key_path: str
    token_url: str
    fhir_base_url: str

    @classmethod
    def from_env(cls) -> "EpicConfig":
        """Create configuration from environment variables."""
        client_id = os.getenv("EPIC_CLIENT_ID")
        if not client_id:
            raise ValueError("EPIC_CLIENT_ID environment variable is required")

        private_key_path = os.getenv("EPIC_PRIVATE_KEY_PATH", "./private_key.pem")
        if not Path(private_key_path).exists():
            raise FileNotFoundError(f"Private key not found at {private_key_path}")

        return cls(
            client_id=client_id,
            private_key_path=private_key_path,
            token_url=os.getenv(
                "EPIC_TOKEN_URL",
                "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
            ),
            fhir_base_url=os.getenv(
                "EPIC_FHIR_BASE_URL",
                "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
            ),
        )


@dataclass
class ServerConfig:
    """MCP server configuration."""

    name: str = "epic-fhir-mcp"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables."""
        return cls(
            name=os.getenv("MCP_SERVER_NAME", "epic-fhir-mcp"),
            version=os.getenv("MCP_SERVER_VERSION", "0.1.0"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
        )


def setup_logging() -> None:
    """Configure logging for the application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
