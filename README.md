# Travel Orchestrator

AI-powered travel planning system with multi-agent orchestration using LangGraph, Anthropic Claude, and MCP.

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/)

## Setup

```bash
# Install dependencies
poetry install

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Run tests
poetry run pytest
```

## Project Structure

```
src/travel_orchestrator/
├── graph/          # LangGraph nodes and state machine
├── state/          # TypedDicts and schemas
├── validators/     # Deterministic validation
├── mcp_servers/    # MCP tool and context servers
├── agents/         # Specialized agents (A2A)
├── models/         # Data models
├── utils/          # Helpers and utilities
└── config/         # Configuration
```
