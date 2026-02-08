```
 _____                    _    ___           _               _             _
|_   _| __ __ ___   _____| |  / _ \ _ __ ___| |__   ___  ___| |_ _ __ __ _| |_ ___  _ __
  | || '__/ _` \ \ / / _ \ | | | | | '__/ __| '_ \ / _ \/ __| __| '__/ _` | __/ _ \| '__|
  | || | | (_| |\ V /  __/ | | |_| | | | (__| | | |  __/\__ \ |_| | | (_| | || (_) | |
  |_||_|  \__,_| \_/ \___|_|  \___/|_|  \___|_| |_|\___||___/\__|_|  \__,_|\__\___/|_|
```

# Travel Orchestrator

**AI-powered travel planning system with multi-agent orchestration.**

An end-to-end travel planning platform that uses LangGraph state machines, MCP (Model Context Protocol) servers, and real-time WebSocket streaming to orchestrate AI agents that research destinations, find hotels, discover activities, optimize itineraries, and present plans for human approval.

---

## Architecture

```mermaid
graph TB
    subgraph Frontend["React SPA (port 3000)"]
        UI[Chat + Planner UI]
        Map[Interactive Map]
        Timeline[Drag-and-Drop Timeline]
        Dashboard[Metrics Dashboard]
        OrcPanel[Orchestrator Panel]
    end

    subgraph API["FastAPI API (port 8000)"]
        REST[REST Endpoints]
        WSOrch[WS /ws/orchestrator]
        WSChat[WS /ws/chat]
        Metrics[/metrics]
    end

    subgraph Graph["LangGraph State Machine"]
        GR[gather_requirements]
        AD[analyze_destination]
        SF[search_flights]
        SH[search_hotels]
        SA[search_activities]
        OI[optimize_itinerary]
        CB[calculate_budget]
        RC[risk_and_policy_check]
        PA[present_for_approval]
        PF[process_feedback]
        BS[book_services]
        GD[generate_documents]
    end

    subgraph MCP["MCP Servers"]
        Weather[Weather MCP<br/>Open-Meteo / OWM]
        Hotels[Hotels MCP<br/>Booking.com / Mock]
        Activities[Activities MCP<br/>Google Places / Mock]
        Context[Context MCP<br/>User Preferences]
    end

    subgraph Infra["Infrastructure"]
        Redis[(Redis)]
        Prometheus[Prometheus]
        Grafana[Grafana]
    end

    UI -->|POST /api/plan| REST
    UI -->|WebSocket| WSChat
    OrcPanel -->|WebSocket| WSOrch
    Dashboard -->|GET /metrics| Metrics

    REST --> Graph
    Graph --> MCP

    AD --> Weather
    AD --> Activities
    SH --> Hotels
    SA --> Activities

    GR --> AD --> SF --> SH --> SA --> OI --> CB
    CB -->|over budget| SF
    CB -->|within budget| RC --> PA
    PA -->|approved| BS --> GD
    PA -->|rejected| PF --> SH

    API --> Redis
    Prometheus --> Metrics
    Grafana --> Prometheus
```

## Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19, TypeScript, Vite | Single-page application |
| **Styling** | Tailwind CSS v4, Framer Motion | Dark theme, animations |
| **State** | Zustand | Client-side state management |
| **Maps** | Mapbox GL + Leaflet fallback | Interactive travel maps |
| **Charts** | Recharts | Dashboard visualizations |
| **Backend** | FastAPI, Uvicorn | REST API + WebSocket |
| **Orchestration** | LangGraph, LangChain | Multi-agent state machine |
| **AI** | Anthropic Claude | LLM-powered planning |
| **Tools** | MCP (Model Context Protocol) | Weather, hotels, activities |
| **Observability** | Prometheus, Grafana | Metrics and monitoring |
| **Cache** | Redis | State persistence |
| **Container** | Docker, Nginx | Production deployment |

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/your-org/travel-orchestrator.git
cd travel-orchestrator
poetry install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — see "API Keys" section below
```

### 3. Run

```bash
# Backend API (port 8000)
poetry run uvicorn travel_orchestrator.api.main:app --port 8000

# Frontend dev server (port 5173) — in another terminal
cd frontend && npm install && npm run dev
```

Or with Docker:

```bash
docker compose up --build
# API: http://localhost:8000
# Frontend: http://localhost:3000
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001
```

## API Keys

| Key | Required | Provider | Purpose |
|-----|----------|----------|---------|
| `ANTHROPIC_API_KEY` | No* | [Anthropic](https://console.anthropic.com/) | LLM for planning intelligence |
| `OPENWEATHERMAP_API_KEY` | No | [OpenWeatherMap](https://openweathermap.org/api) | Weather data (fallback) |
| `RAPIDAPI_KEY` | No | [RapidAPI](https://rapidapi.com/) | Booking.com hotel search |
| `GOOGLE_MAPS_API_KEY` | No | [Google Cloud](https://console.cloud.google.com/) | Google Places activities |
| `VITE_MAPBOX_TOKEN` | No | [Mapbox](https://www.mapbox.com/) | Mapbox GL map tiles |
| `LANGSMITH_API_KEY` | No | [LangSmith](https://smith.langchain.com/) | LLM tracing/debugging |
| `REDIS_URL` | No | — | Cache (default: in-memory) |

> **\*Demo Mode**: The system works without any API keys. All providers have mock fallbacks that generate realistic sample data. See "Demo Mode" below.

## Demo Mode

The system is designed for presentations without requiring API keys:

```bash
# Start with zero configuration
docker compose up --build

# Or locally
poetry run uvicorn travel_orchestrator.api.main:app --port 8000
```

**What works in demo mode:**
- Weather forecasts (mock data with realistic temperatures)
- Hotel search (5 scored mock hotels per destination)
- Activity discovery (15+ mock activities with categories)
- Complete itinerary optimization
- Interactive map with pins and routes
- Real-time orchestrator panel with tool call visualization
- Timeline drag-and-drop
- Budget tracking and risk analysis
- PDF itinerary generation

**Demo flow:**
1. Open http://localhost:5173 (dev) or http://localhost:3000 (Docker)
2. Fill in destination, dates, budget in the Planner
3. Watch the Orchestrator panel show real-time node execution
4. Explore Results: itinerary, hotels, activities, weather, map
5. Drag activities in the Timeline to reorder
6. Approve or reject the plan

## Project Structure

```
travel-orchestrator/
├── src/travel_orchestrator/
│   ├── api/                    # FastAPI API layer
│   │   ├── main.py             # App, REST endpoints, WebSocket handlers
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── ws_manager.py       # WebSocket connection manager
│   │   ├── ws_orchestrator.py  # Orchestrator event broadcasting
│   │   └── callbacks.py        # LangGraph → WebSocket callbacks
│   ├── graph/                  # LangGraph state machine
│   │   ├── planner_graph.py    # 12-node graph definition
│   │   ├── edges.py            # Conditional routing logic
│   │   └── nodes/              # Individual graph nodes
│   │       ├── analyze_destination.py
│   │       ├── search_hotels.py
│   │       ├── search_activities.py
│   │       ├── optimize_itinerary.py
│   │       ├── present_for_approval.py  # HITL interrupt
│   │       └── ...
│   ├── mcp_servers/            # MCP tool servers
│   │   ├── weather/            # Open-Meteo + OWM + mock
│   │   ├── hotels/             # Booking.com + mock
│   │   ├── activities/         # Google Places + mock
│   │   └── context/            # User preferences
│   ├── state/models.py         # TypedDict state schema
│   ├── validators/             # Itinerary & weather validators
│   ├── multimodal/             # Audio, image, PDF processing
│   ├── output/                 # Map (Folium) & PDF (ReportLab) generation
│   ├── observability/          # Prometheus metrics
│   └── frontend/               # Legacy Gradio app (deprecated)
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── Cards/          # Hotel, Activity, Weather, Summary cards
│   │   │   ├── Chat/           # Chat interface + approval panel
│   │   │   ├── Dashboard/      # Stats, budget, agenda, risk flags
│   │   │   ├── Layout/         # AppShell, Header, Sidebar, Footer
│   │   │   ├── Map/            # Mapbox + Leaflet interactive maps
│   │   │   ├── Orchestrator/   # Pipeline visualizer, tool calls, logs
│   │   │   ├── Timeline/       # Drag-and-drop itinerary editor
│   │   │   └── ui/             # Button, Input, GlassPanel, Skeleton...
│   │   ├── stores/             # Zustand state (plan, chat, map, timeline...)
│   │   ├── services/           # REST client, WebSocket, API
│   │   ├── pages/              # Planner, Results, Dashboard
│   │   └── types/              # TypeScript interfaces
│   ├── Dockerfile              # Multi-stage Node build
│   └── nginx.conf              # Production Nginx config
├── tests/
│   ├── unit/                   # 999+ unit tests
│   └── integration/            # Integration tests
├── docs/                       # Architecture, config, API reference
├── docker-compose.yml          # Full stack: API, Frontend, Redis, Prometheus, Grafana
├── Dockerfile                  # Python API container
├── prometheus.yml              # Metrics scraping config
└── pyproject.toml              # Poetry dependencies
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/plan` | Run planning pipeline (JSON body) |
| `POST` | `/api/plan/form` | Run planning pipeline (FormData + files) |
| `GET` | `/api/trip/{id}` | Get trip plan by ID |
| `PATCH` | `/api/trip/{id}/itinerary` | Update itinerary (drag-drop) |
| `POST` | `/api/trip/{id}/approve` | Approve or reject a plan |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/dashboard` | Monitoring dashboard |
| `WS` | `/ws/orchestrator` | Real-time pipeline events |
| `WS` | `/ws/chat` | Chat streaming |

## Testing

```bash
# Backend tests (999+ tests)
PYTHONPATH=src python -m pytest tests/ -v

# Frontend type check
cd frontend && npx tsc -b

# Frontend build
cd frontend && npm run build
```

## Deployment

See [docs/deployment.md](docs/deployment.md) for detailed deployment instructions including:
- Docker Compose production setup
- Environment variable reference
- Prometheus metrics and PromQL queries
- Grafana dashboard configuration

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run tests: `poetry run pytest && cd frontend && npx tsc -b`
4. Commit with descriptive messages
5. Open a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for details.
