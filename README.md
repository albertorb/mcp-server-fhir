# Epic FHIR MCP Server

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.1+-green.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready Model Context Protocol (MCP) server that connects LLMs to Epic's FHIR API. Supports both **stdio** (for Claude Desktop) and **HTTP/SSE** transports with OAuth2 backend systems authentication.

## Features

- **OAuth2 Backend Systems Flow** - Secure server-to-server authentication with JWT
- **Epic FHIR R4 API** - Access patient data, medications, observations, and more
- **Dual Transport** - Stdio for Claude Desktop, Streamable HTTP for web clients

## Architecture

**Stdio Transport (Claude Desktop):**
```
┌─────────────┐    stdin/stdout    ┌─────────────┐    OAuth2/FHIR    ┌─────────────┐
│   Claude    │ ◄───────────────► │ MCP Server  │ ◄──────────────► │  Epic FHIR  │
│   Desktop   │                    │  (Python)   │                   │     API     │
└─────────────┘                    └─────────────┘                   └─────────────┘
```

**Streamable HTTP Transport (Web Clients):**
```
┌─────────────┐  Streamable HTTP  ┌─────────────┐    OAuth2/FHIR    ┌─────────────┐
│   Web/API   │ ◄────────────────► │ MCP Server  │ ◄──────────────► │  Epic FHIR  │
│   Client    │                    │  (Python)   │                   │     API     │
└─────────────┘                    └─────────────┘                   └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Epic FHIR Sandbox account ([Sign up](https://fhir.epic.com))
- OpenSSL (for key generation)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd fhir-epic-mcpserver

# Install dependencies
uv sync
# or: pip install -e .
```

### 2. Generate Keys and JWKS

```bash
# Run setup script to generate RSA keys and JWKS
uv run python create_keys.py
```

This will create:
- `private_key.pem` - Your private key (keep secret!)
- `public_key.pem` - Public key
- `certificate.pem` - X.509 certificate
- `jwks.json` - JSON Web Key Set for Epic
- `.env` - Environment configuration

### 3. Host JWKS Publicly

Epic requires your JWKS to be accessible via public HTTPS URL.

**Option A: GitHub Gist (Quick)**
1. Go to https://gist.github.com
2. Create new gist with filename `jwks.json`
3. Paste contents from your `jwks.json` file
4. Create public gist
5. Click "Raw" and copy the URL

**Option B: Production Hosting**
- Your domain: `https://yourdomain.com/.well-known/jwks.json`
- AWS S3, Azure Blob, or Google Cloud Storage (public)

### 4. Configure Epic App

1. Go to https://fhir.epic.com/Developer/Apps
2. Create **Backend Systems** app
3. Select FHIR R4 APIs you need:
   - Patient.Read
   - Observation.Read
   - Condition.Read
   - MedicationRequest.Read
   - AllergyIntolerance.Read
   - Immunization.Read
4. In **Non-Production** section:
   - Add your JWKS URL
   - Click **Test** to validate
   - Click **Save & Ready for Sandbox**
5. **Wait 30 minutes** for Epic to sync

### 5. Configure Environment

Update `.env` with your Epic credentials:

```bash
EPIC_CLIENT_ID=your-client-id-from-epic
EPIC_PRIVATE_KEY_PATH=./private_key.pem
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
EPIC_FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4

# Server config
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### 6. Run Server

```bash
# For Claude Desktop (stdio mode - default)
uv run python src/server.py

# For HTTP/SSE mode (web/API usage)
uv run python src/server.py --transport sse --port 8000

# Production with uvicorn (SSE mode)
uv run uvicorn src.server:app --host 0.0.0.0 --port 8000
```

**Stdio mode** runs on `stdin/stdout` for Claude Desktop  
**SSE mode** runs HTTP server on `http://localhost:8000`

## Available Tools

The MCP server exposes these tools to LLMs:

| Tool | Description | Required Args |
|------|-------------|---------------|
| `get_patient` | Get patient demographics | `patient_id` |
| `search_patients` | Search patients by name/DOB | `family`, `given`, `birthdate`, `gender` |
| `get_patient_conditions` | Get medical conditions | `patient_id` |
| `get_patient_medications` | Get medications/prescriptions | `patient_id` |
| `get_patient_observations` | Get labs/vitals | `patient_id`, `category` (optional) |
| `get_patient_allergies` | Get allergies | `patient_id` |
| `get_patient_immunizations` | Get vaccination history | `patient_id` |
| `get_patient_procedures` | Get procedures | `patient_id` |

## Testing with Epic Sandbox

Epic provides test patients with realistic data:

| Patient Name | FHIR ID | Available Data |
|--------------|---------|----------------|
| Camila Lopez | `erXuFYUfucBZaryVksYEcMg3` | Medications, Labs, Procedures |
| Derrick Lin | `eq081-VQEgP8drUUqCWzHfw3` | Conditions, CarePlans |
| Desiree Powell | `eAB3mDIBBcyUKviyzrxsnAw3` | Immunizations, Vitals |

See full list: https://fhir.epic.com/Documentation?docId=testpatients

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "epic-fhir": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/path/to/fhir-epic-mcpserver/src/server.py"
      ],
      "env": {
        "EPIC_CLIENT_ID": "your-client-id-here",
        "EPIC_PRIVATE_KEY_PATH": "/path/to/fhir-epic-mcpserver/private_key.pem",
        "EPIC_TOKEN_URL": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        "EPIC_FHIR_BASE_URL": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
      }
    }
  }
}
```

**Important:** 
- Use **absolute paths** for the script and private key
- Replace `your-client-id-here` with your actual Epic Client ID
- Replace `/path/to/fhir-epic-mcpserver` with your actual project path
- Restart Claude Desktop after updating the config

**Quick setup:**
1. Copy `claude_desktop_config.example.json` content
2. Update the paths to your actual project location
3. Add your Epic Client ID
4. Paste into Claude Desktop config at:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Other MCP Clients (HTTP/SSE)

For web-based or HTTP clients, run in SSE mode:

```bash
uv run python src/server.py --transport sse --port 8000
```

Connect to SSE endpoint: `http://localhost:8000/sse`

## Development

### Project Structure

```
epic-fhir-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py          # HTTP/SSE MCP server
│   ├── epic_client.py     # Epic OAuth2 + FHIR client
│   ├── tools.py           # MCP tool definitions
│   └── config.py          # Configuration management
├── create_keys.py         # Key generation script
├── pyproject.toml         # Dependencies
├── .env.example           # Environment template
└── README.md
```

### Running Tests

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=src
```

### Code Quality

```bash
# Format code
uv run ruff format src/

# Lint
uv run ruff check src/
```

## Troubleshooting

### `invalid_client` Error

**Causes:**
- App not "Ready for Sandbox"
- Epic configuration not synced (wait 30 min)
- Wrong client ID
- JWKS URL not accessible

**Solutions:**
1. Verify app status in Epic portal
2. Wait 30 minutes after configuration changes
3. Test JWKS URL: `curl https://your-jwks-url`
4. Check `kid` matches between JWT and JWKS

### `401 Unauthorized` on FHIR Requests

**Causes:**
- Token expired (1-hour lifetime)
- Missing Authorization header
- Insufficient scopes

**Solutions:**
- Token is cached automatically
- Check logs for authentication errors
- Verify required scopes in Epic app config

### Connection Issues

```bash
# Check server is running
curl http://localhost:8000/sse

# View logs
LOG_LEVEL=DEBUG uv run python src/server.py
```

## OpenAI Agent Integration

This MCP server can be used with the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) to create AI agents that can interact with Epic FHIR data.

### Quick Start with Agent

1. **Install the OpenAI Agents SDK**:
   ```bash
   pip install openai-agents
   # or
   uv add openai-agents
   ```

2. **Set your OpenAI API key**:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. **Run the simple test agent**:
   ```bash
   python test_agent_simple.py
   ```

### Example Agent Code

```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

async def main():
    async with MCPServerStdio(
        name="Epic FHIR",
        params={"command": "uv", "args": ["run", "python", "-m", "src.server"]},
    ) as mcp_server:
        agent = Agent(
            name="FHIR Assistant",
            instructions="You are a helpful medical assistant.",
            mcp_servers=[mcp_server],
        )
        
        result = await Runner.run(
            starting_agent=agent,
            input="Search for patient Derrick Borer"
        )
        print(result.final_output)

asyncio.run(main())
```
