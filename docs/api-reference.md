# Referencia da API

## Graph

### `graph/planner_graph.py`

```python
compile_graph() -> CompiledStateGraph
```

Compila o grafo LangGraph com MemorySaver. Retorna grafo pronto para `ainvoke()`.

```python
graph = compile_graph()
result = await graph.ainvoke(state, config={"configurable": {"thread_id": "abc"}})
```

### `graph/edges.py`

```python
should_optimize_costs(state: TravelPlannerCore) -> str
```
Retorna `"optimize_costs"` ou `"proceed"` baseado no budget.

```python
process_approval_decision(state: TravelPlannerCore) -> str
```
Retorna `"approved"` ou `"rejected"` baseado em `approval_status`.

```python
determine_revision_target(state: TravelPlannerCore) -> str
```
Retorna `"search_flights"`, `"search_hotels"` ou `"search_activities"` baseado no feedback.

## Nodes

Todos os nodes seguem a assinatura `async def node(state: dict) -> dict`.

| Node | Modulo | Descricao |
|------|--------|-----------|
| `gather_requirements_node` | `graph/nodes/gather_requirements.py` | Validacao e enriquecimento de inputs |
| `analyze_destination_node` | `graph/nodes/analyze_destination.py` | Analise climatica e cultural do destino |
| `search_hotels_node` | `graph/nodes/search_hotels.py` | Busca e selecao de hoteis |
| `search_activities_node` | `graph/nodes/search_activities.py` | Busca e selecao de atividades |
| `optimize_itinerary_node` | `graph/nodes/optimize_itinerary.py` | Otimizacao hibrida LLM + deterministica |
| `calculate_budget_node` | `graph/nodes/calculate_budget.py` | Reconciliacao de custos |
| `risk_and_policy_check_node` | `graph/nodes/risk_check.py` | Verificacoes de seguranca e politica |
| `present_for_approval_node` | `graph/nodes/present_for_approval.py` | Checkpoint HITL com interrupt() |

## MCP Servers

### Weather Client

```python
from travel_orchestrator.mcp_servers.weather.client import (
    get_weather_forecast,
    get_weather_alerts,
)

forecasts = await get_weather_forecast("Paris", "2026-07-01", "2026-07-08")
# -> list[WeatherForecast]

alerts = await get_weather_alerts("Paris")
# -> list[dict]
```

### Hotels Client

```python
from travel_orchestrator.mcp_servers.hotels.client import search_hotels

hotels = await search_hotels(
    destination="Paris",
    check_in="2026-07-01",
    check_out="2026-07-08",
    guests=2,
    location_centrality=0.5,
    min_stars=3,
    amenities=["wifi", "pool"],
)
# -> list[dict]
```

### Activities Client

```python
from travel_orchestrator.mcp_servers.activities.client import discover_activities

activities = await discover_activities(
    destination="Paris",
    interests=["museum", "gastronomy"],
    start_date="2026-07-01",
    end_date="2026-07-08",
    budget_per_day=100.0,
)
# -> list[dict]
```

### Context Client

```python
from travel_orchestrator.mcp_servers.context.client import (
    get_user_preferences,
    get_travel_style,
    get_accommodation_preferences,
)

prefs = await get_user_preferences("user-123")
# -> dict com travel_style, dietary_restrictions, past_trips, etc.

style = await get_travel_style("user-123")
# -> dict com pace, budget_preference, etc.
```

## Multimodal

### Audio Processor

```python
from travel_orchestrator.multimodal.audio_processor import (
    populate_state_from_audio,
    transcribe_audio,
    extract_requirements_from_transcript,
)

# Pipeline completo: audio -> state dict
state = await populate_state_from_audio("/path/to/voice.mp3")
# -> dict compativel com TravelPlannerCore

# Passo a passo
transcript = await transcribe_audio("/path/to/voice.mp3")
# -> str (texto transcrito)

requirements = await extract_requirements_from_transcript(transcript)
# -> AudioRequirements dict
```

**Formatos suportados**: `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.m4a`, `.wav`, `.webm`
**Tamanho maximo**: 25 MB

### Image Analyzer

```python
from travel_orchestrator.multimodal.image_analyzer import analyze_inspiration_image

vibe = await analyze_inspiration_image("/path/to/photo.jpg")
# -> TravelVibe dict:
# {
#     "destination_suggestions": ["Barcelona", "Madrid"],
#     "vibe_tags": ["sunny", "vibrant"],
#     "budget_tier_guess": "mid",       # "budget" | "mid" | "luxury"
#     "season_preference": "summer",
#     "activity_bias": ["beach", "food"],
# }
```

**Formatos suportados**: `.jpg`, `.jpeg`, `.png`, `.webp`
**Tamanho maximo**: 20 MB

### PDF Parser

```python
from travel_orchestrator.multimodal.pdf_parser import parse_competitor_offer_pdf

offer = await parse_competitor_offer_pdf("/path/to/offer.pdf")
# -> CompetitorOffer dict:
# {
#     "destination": "Lisboa",
#     "price": 4500.0,
#     "currency": "BRL",
#     "duration_days": 7,
#     "highlights": ["Sintra", "Fado"],
#     "hotel_name": "Hotel Avenida",
#     "raw_text": "...",
# }
```

**Tamanho maximo**: 50 MB

## Validators

### ItineraryValidator

```python
from travel_orchestrator.validators.itinerary_validator import ItineraryValidator

result = ItineraryValidator.validate_geographic_coherence(
    activities=activities,          # list[Activity]
    hotel=hotel,                    # HotelOption
    max_travel_time_minutes=90,
)
# -> ValidationResult

result = ItineraryValidator.validate_timing_conflicts(
    activities=day_activities,      # list[Activity]
    date="2026-07-01",
)
# -> ValidationResult

result = ItineraryValidator.validate_budget_constraints(state)
# -> ValidationResult
```

### WeatherValidator

```python
from travel_orchestrator.validators.weather_validator import WeatherValidator

result = WeatherValidator.validate_outdoor_activities(
    activities=outdoor_activities,  # list[Activity]
    forecast=day_forecast,          # WeatherForecast
)
# -> ValidationResult

result = WeatherValidator.validate_weather_suitability(forecast)
# -> ValidationResult
```

### ValidationResult

```python
{
    "is_valid": bool,
    "issues": ["descricao do problema", ...],
    "severity": "error" | "warning" | "info",
    "suggested_fixes": ["sugestao de correcao", ...],
}
```

## Output

### Map Generator

```python
from travel_orchestrator.output.map_generator import (
    generate_map_from_state,
    generate_interactive_map,
)

# A partir do state completo
path = generate_map_from_state(state, "/tmp/map.html")
# -> str (caminho absoluto) ou "" se dados insuficientes

# Direto com dados estruturados
path = generate_interactive_map(
    hotel=hotel_option,                    # HotelOption
    activities_by_day={"1": [act1, act2]}, # dict[str, list[Activity]]
    destination="Paris",
    output_path="/tmp/map.html",
)
# -> str (caminho absoluto)
```

Gera mapa HTML interativo com Folium:
- Marcador do hotel (vermelho, icone home)
- Marcadores de atividades por dia (cores diferentes)
- Rotas hotel -> atividades -> hotel (PolyLine)
- Layers toggleaveis por dia (LayerControl)

### PDF Generator

```python
from travel_orchestrator.output.pdf_generator import (
    generate_pdf_from_state,
    generate_itinerary_pdf,
)

# A partir do state completo
path = generate_pdf_from_state(state, "/tmp/itinerary.pdf")
# -> str (caminho absoluto) ou "" se dados insuficientes

# Direto com dados estruturados
path = generate_itinerary_pdf(
    destination="Paris",
    dates={"start_date": "2026-07-01", "end_date": "2026-07-08"},
    budget={"total": 5000, "currency": "EUR"},
    hotel=hotel_option,
    activities_by_day={"1": [act1, act2]},
    itinerary_days=itinerary.days,
    cost_breakdown={"flights": 800, "hotel": 1400, "activities": 600, "total": 2800},
    risk_flags=["weather: rain expected day 3"],
    plan_id="plan_abc123",
    output_path="/tmp/itinerary.pdf",
)
```

Gera PDF A4 com ReportLab:
- Capa com destino e datas
- Resumo executivo (tabela de custos, hotel, riscos)
- Itinerario dia-a-dia (atividades, horarios, clima)
- Breakdown de budget
- Vouchers (hotel + atividades com booking)

## Observability

### Metrics

```python
from travel_orchestrator.observability.metrics import (
    track_node_execution,
    track_planning,
    record_plan_approval,
    record_plan_cost,
    get_metrics,
    reset_metrics,
)

# Decoradores
@track_node_execution("analyze_destination")
async def my_node(state):
    ...

@track_planning()
async def plan_trip(...):
    ...

# Helpers
record_plan_approval("approved")   # ou "rejected"
record_plan_cost(2.50)

# Exposicao
raw_bytes = get_metrics()          # Prometheus text format

# Isolamento de testes
reset_metrics()                    # Zera todos os contadores
```

### Server

```python
# Endpoints FastAPI (porta 8000 em producao, 9090 local)

GET /health     # -> {"status": "healthy"}
GET /metrics    # -> Prometheus text format
GET /dashboard  # -> Dashboard HTML com Chart.js
```

## Frontend

### FastAPI SPA

```python
from travel_orchestrator.frontend.server import app

# Executar com uvicorn
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=7860)
```

#### Endpoints

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/` | Serve a SPA (Tailwind CSS) |
| POST | `/api/plan` | Executa pipeline de planejamento |
| POST | `/api/approve` | Aprovacao/rejeicao do plano |
| GET | `/api/map/{filename}` | Serve mapa HTML gerado |
| GET | `/api/pdf/{filename}` | Download PDF gerado |
| GET | `/health` | Health check |
| GET | `/metrics` | Metricas Prometheus |
| GET | `/dashboard` | Dashboard de monitoramento |

### Business Logic

```python
from travel_orchestrator.frontend.app import (
    plan_trip,
    handle_approval,
)

# Pipeline principal
plan_json, map_html, pdf_path = await plan_trip(
    destination="Paris",
    start_date="2026-07-01",
    end_date="2026-07-08",
    budget=5000.0,
    currency="EUR",
    group_size=2,
    interests_text="museum, gastronomy",
    audio_file=None,
    image_file=None,
    pdf_file=None,
)

# Aprovacao/rejeicao
msg = await handle_approval("approved", "")
msg = await handle_approval("rejected", "Hotel muito longe do centro")
```

## Logging

```python
from travel_orchestrator.utils.logging import (
    get_logger,
    setup_logging,
    log_execution,
    log_node_execution,
    add_context,
)

logger = get_logger(__name__)
logger.info("event_name", key="value")

# Decoradores
@log_execution
async def my_function():
    ...

@log_node_execution("node_name")
async def my_node(state):
    ...

# Contexto temporario
with add_context(plan_id="abc-123", user_id="u-1"):
    logger.info("processing")  # inclui plan_id e user_id
```
