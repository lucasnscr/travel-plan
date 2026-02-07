# Plano de Evolucao — Travel Orchestrator

> Baseado em: `docs/ANALYSIS.md` (commit `180b84f`)
> Data: 2026-02-06
> Status do projeto: Alpha funcional (8/12 nodes, 4 MCP servers com mock, frontend SPA basico)

---

## Indice

1. [Visao Geral e Principios](#1-visao-geral-e-principios)
2. [Fases de Implementacao](#2-fases-de-implementacao)
3. [Fase 0 — Fundacao e Correcoes](#3-fase-0--fundacao-e-correcoes)
4. [Fase 1 — MCPs Reais](#4-fase-1--mcps-reais)
5. [Fase 2 — Frontend React Premium](#5-fase-2--frontend-react-premium)
6. [Fase 3 — Multimodalidade Visual](#6-fase-3--multimodalidade-visual)
7. [Fase 4 — Observabilidade Visual](#7-fase-4--observabilidade-visual)
8. [Dependencias entre Tarefas](#8-dependencias-entre-tarefas)
9. [Novas Dependencias (pyproject.toml)](#9-novas-dependencias-pyprojecttoml)
10. [Novas Variaveis de Ambiente](#10-novas-variaveis-de-ambiente)
11. [Inventario de Arquivos](#11-inventario-de-arquivos)
12. [Riscos e Mitigacoes](#12-riscos-e-mitigacoes)

---

## 1. Visao Geral e Principios

### Objetivo

Evoluir o Travel Orchestrator de alpha funcional para um **sistema demonstravel em apresentacao**, com dados reais de APIs externas, frontend React premium com mapa interativo, e painel de observabilidade que mostra o grafo LangGraph executando em tempo real.

### Principios

- **Mock first, real second**: Toda integracao nova mantem fallback para mock. Testes nunca dependem de API externa.
- **Backend estavel antes de frontend**: MCPs reais devem funcionar antes de serem consumidos pelo React.
- **WebSocket para tempo real**: O painel de observabilidade e o progresso do pipeline usam WebSocket, nao polling.
- **Separacao de concerns**: Backend (FastAPI) serve API REST + WebSocket. Frontend (React/Vite) e build separado servido como static.

### Stack de Evolucao

| Camada | Atual | Evolucao |
|--------|-------|----------|
| Frontend | HTML estatico + Tailwind (560 LOC) | Vite + React + TypeScript + Tailwind |
| Mapa | Folium (server-side HTML) | Mapbox GL JS (client-side interativo) |
| Weather API | OpenWeatherMap (parcial) + mock | Open-Meteo (gratuita, sem key) |
| Hotels API | Enuygun MCP (adapter pronto) + mock | Booking.com via RapidAPI (SerpAPI fallback) |
| Activities API | Mock only | Google Places API (New) |
| Maps/Routing | Nenhum | Google Maps API (Directions, Distance Matrix) |
| Tempo real | Nenhum | WebSocket (FastAPI → React) |
| State management | Dict global (`_last_result_state`) | Redis + session-based |

---

## 2. Fases de Implementacao

```
Fase 0 (Fundacao)          ████░░░░░░░░░░░░░░░░  ~2 dias
Fase 1 (MCPs Reais)        ░░░░████████░░░░░░░░  ~5 dias
Fase 2 (Frontend React)    ░░░░░░░░░░░░████████  ~6 dias
Fase 3 (Multimodalidade)   ░░░░░░░░░░░░░░░░████  ~3 dias
Fase 4 (Observabilidade)   ░░░░░░░░░░░░░░░░░███  ~3 dias
                            ─────────────────────
                            Total: ~19 dias de dev
```

**Dependencias entre fases:**
- Fase 1 pode comecar apos Fase 0
- Fase 2 pode comecar apos Fase 0 (paralelo parcial com Fase 1)
- Fase 3 depende de Fase 1 (Google Places Photos) e Fase 2 (mapa React)
- Fase 4 depende de Fase 0 (WebSocket) e Fase 2 (shell React)

---

## 3. Fase 0 — Fundacao e Correcoes

> Resolve gaps criticos do ANALYSIS.md que bloqueiam as fases seguintes.

### Tarefa 0.1: Adicionar campos ausentes em Settings

**Problema**: `openweathermap_api_key` e usado em `weather/server.py:39` via `getattr()` mas nao existe em `Settings`. Novos campos necessarios para APIs reais.

**Arquivos modificados:**
- `src/travel_orchestrator/config/settings.py`

**Campos a adicionar:**
```python
# Weather
openweathermap_api_key: str | None = Field(None, description="OpenWeatherMap API key (legacy)")
open_meteo_base_url: str = Field("https://api.open-meteo.com/v1", description="Open-Meteo base URL")

# Hotels
rapidapi_key: str | None = Field(None, description="RapidAPI key for Booking.com")
serpapi_key: str | None = Field(None, description="SerpAPI key (fallback hotel search)")

# Google
google_maps_api_key: str | None = Field(None, description="Google Maps Platform API key")
google_places_api_key: str | None = Field(None, description="Google Places API key (pode ser o mesmo do Maps)")

# Frontend
mapbox_access_token: str | None = Field(None, description="Mapbox GL JS access token")

# WebSocket
ws_enabled: bool = Field(True, description="Habilitar WebSocket para observabilidade")
```

**Esforco**: 0.5h

---

### Tarefa 0.2: Adicionar `flight_options` ao state

**Problema**: `calculate_budget.py:106` faz `state.get("flight_options", [])` com `# type: ignore`, mas o campo nao existe em `TravelPlannerCore`.

**Arquivos modificados:**
- `src/travel_orchestrator/state/models.py`

**Mudanca:**
```python
class TravelPlannerCore(TypedDict):
    # ... campos existentes ...
    flight_options: list[FlightOption]  # NOVO
```

**Esforco**: 0.25h

---

### Tarefa 0.3: Implementar WebSocket no FastAPI

**Motivo**: Base necessaria para Fase 2 (progresso em tempo real) e Fase 4 (painel de observabilidade).

**Arquivos modificados:**
- `src/travel_orchestrator/frontend/server.py` — adicionar endpoint `ws://`

**Arquivos criados:**
- `src/travel_orchestrator/frontend/ws_manager.py` — ConnectionManager para broadcast de eventos

**Design:**
```python
# ws_manager.py
class PlanningEventManager:
    """Gerencia conexoes WebSocket e broadcast de eventos do pipeline."""

    async def connect(self, websocket, plan_id: str) -> None: ...
    async def disconnect(self, websocket, plan_id: str) -> None: ...
    async def broadcast(self, plan_id: str, event: dict) -> None: ...

# Tipos de evento:
# {"type": "node_start", "node": "search_hotels", "timestamp": "..."}
# {"type": "node_end", "node": "search_hotels", "duration_ms": 1234, "timestamp": "..."}
# {"type": "mcp_call", "server": "hotels", "tool": "search_hotels", "timestamp": "..."}
# {"type": "mcp_result", "server": "hotels", "tool": "search_hotels", "result_count": 15}
# {"type": "validation", "validator": "itinerary", "issues": [...]}
# {"type": "progress", "pct": 0.6, "message": "Optimizing itinerary..."}
# {"type": "complete", "plan_id": "plan_abc123"}
```

**Esforco**: 1h

---

### Tarefa 0.4: Adicionar CORS ao FastAPI

**Problema**: Frontend React rodara em porta separada durante dev (Vite em :5173, FastAPI em :7860).

**Arquivos modificados:**
- `src/travel_orchestrator/frontend/server.py`

**Mudanca:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Esforco**: 0.25h

---

### Tarefa 0.5: Migrar estado de aprovacao para Redis

**Problema**: `_last_result_state` e um dict global — nao funciona com multiplos usuarios. Redis ja esta provisionado no docker-compose mas nao e usado.

**Arquivos modificados:**
- `src/travel_orchestrator/frontend/app.py` — substituir `_last_result_state` por Redis
- `src/travel_orchestrator/frontend/server.py` — passar `plan_id` na aprovacao

**Arquivos criados:**
- `src/travel_orchestrator/frontend/state_store.py` — abstraction layer (Redis + fallback in-memory)

**Esforco**: 1.5h

---

**Esforco total Fase 0: ~3.5h (~0.5 dia)**

---

## 4. Fase 1 — MCPs Reais

### Tarefa 1.1: Weather — Open-Meteo API

**Por que Open-Meteo**: Gratuita, sem API key, sem rate limit agressivo, cobre forecast (16 dias), historico, qualidade do ar, e elevacao.

**Endpoints a usar:**
| Endpoint | URL | Dados |
|----------|-----|-------|
| Forecast | `api.open-meteo.com/v1/forecast` | Temp, chuva, vento, condicao, UV index (ate 16 dias) |
| Historical | `archive-api.open-meteo.com/v1/archive` | Dados historicos para destinos com datas longinquas |
| Air Quality | `air-quality-api.open-meteo.com/v1/air-quality` | PM2.5, PM10, AQI europeu |
| Geocoding | `geocoding-api.open-meteo.com/v1/search` | Nome → lat/lon (substitui OpenWeatherMap geocoding) |

**Arquivos criados:**
- `src/travel_orchestrator/mcp_servers/weather/open_meteo_provider.py`

**Arquivos modificados:**
- `src/travel_orchestrator/mcp_servers/weather/server.py` — dispatch para Open-Meteo em vez de OWM
- `src/travel_orchestrator/mcp_servers/weather/client.py` — nova tool `get_air_quality`
- `src/travel_orchestrator/state/models.py` — adicionar `air_quality` em `WeatherForecast` e `uv_index`
- `tests/unit/mcp_servers/test_weather.py` — testes para Open-Meteo provider

**Implementacao `open_meteo_provider.py`:**

```python
class OpenMeteoProvider:
    """Cliente para Open-Meteo API (gratuita, sem key)."""

    BASE_URL = "https://api.open-meteo.com/v1"
    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    async def geocode(self, destination: str) -> tuple[float, float]:
        """Converte nome de cidade em lat/lon."""

    async def get_forecast(
        self, destination: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Forecast diario com: temp_max, temp_min, rain_chance,
        wind_speed, condition, uv_index, rain_start."""

    async def get_air_quality(
        self, lat: float, lon: float
    ) -> dict:
        """AQI europeu, PM2.5, PM10."""

    async def get_historical(
        self, destination: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Dados historicos para datas fora do range de forecast."""
```

**Nova tool MCP exposta:**
```
get_air_quality(destination) -> {aqi, pm2_5, pm10, category}
```

**Fallback chain:**
```
Open-Meteo API → OpenWeatherMap (se key existir) → Mock Provider
```

**Esforco**: 4h

---

### Tarefa 1.2: Hotels — Booking.com via RapidAPI

**Opcoes analisadas:**

| Provider | Custo | Dados | Dificuldade |
|----------|-------|-------|-------------|
| Booking.com (RapidAPI) | $0.01/req (Freemium tier: 500 free) | Precos, fotos, amenidades, reviews | Media |
| SerpAPI Hotels | $50/mo (5000 searches) | Google Hotels results | Media |
| Enuygun MCP (existente) | Gratuito | Limitado ao ecossistema | Ja implementado |

**Estrategia**: Booking.com via RapidAPI como primario, com Enuygun como secundario e mock como fallback.

**Endpoint RapidAPI:** `booking-com15.p.rapidapi.com`

| Endpoint | Uso |
|----------|-----|
| `/api/v1/hotels/searchDestination` | Resolve destino em `dest_id` |
| `/api/v1/hotels/searchHotels` | Busca hoteis com precos |
| `/api/v1/hotels/getHotelDetails` | Detalhes, fotos, amenidades |

**Arquivos criados:**
- `src/travel_orchestrator/mcp_servers/hotels/booking_provider.py`

**Arquivos modificados:**
- `src/travel_orchestrator/mcp_servers/hotels/server.py` — adicionar dispatch para Booking
- `src/travel_orchestrator/mcp_servers/hotels/models.py` — adicionar campos `photos`, `booking_url`
- `tests/unit/mcp_servers/test_hotels.py` — testes para Booking provider

**Implementacao `booking_provider.py`:**

```python
class BookingProvider:
    """Cliente para Booking.com via RapidAPI."""

    BASE_URL = "https://booking-com15.p.rapidapi.com/api/v1"

    def __init__(self, rapidapi_key: str):
        self.headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
        }

    async def search_destination(self, query: str) -> str:
        """Resolve nome do destino em dest_id do Booking."""

    async def search_hotels(
        self, dest_id: str, check_in: str, check_out: str, guests: int
    ) -> list[dict]:
        """Busca hoteis com precos reais. Retorna dicts normalizados."""

    async def get_hotel_details(self, hotel_id: str) -> dict:
        """Detalhes completos: fotos, amenidades, reviews."""
```

**Fallback chain:**
```
Booking.com RapidAPI → Enuygun MCP (adapter existente) → Mock Provider
```

**Campos novos em `HotelResult` (models.py):**
```python
photos: list[str] = []           # URLs das fotos
booking_url: str | None = None   # Deep link para reserva
review_count: int | None = None  # Numero de reviews
```

**Esforco**: 5h

---

### Tarefa 1.3: Activities — Google Places API (New)

**Por que Google Places API (New):** Cobertura global, fotos de alta qualidade, ratings, horarios de funcionamento, categorias detalhadas, e preco incluso na plataforma Google Maps.

**Endpoints a usar:**

| Endpoint | Uso |
|----------|-----|
| `places.googleapis.com/v1/places:searchText` | Text Search (principal) |
| `places.googleapis.com/v1/places/{id}` | Detalhes do lugar |
| `places.googleapis.com/v1/places/{id}/photos/{name}/media` | Foto do lugar |

**Arquivos criados:**
- `src/travel_orchestrator/mcp_servers/activities/google_places_provider.py`

**Arquivos modificados:**
- `src/travel_orchestrator/mcp_servers/activities/server.py` — dispatch para Google Places
- `src/travel_orchestrator/mcp_servers/activities/client.py` — expor `get_place_photo`
- `src/travel_orchestrator/state/models.py` — adicionar `photos`, `rating`, `place_id` em `Activity`
- `tests/unit/mcp_servers/test_activities.py` — testes para Google Places provider

**Implementacao `google_places_provider.py`:**

```python
class GooglePlacesProvider:
    """Cliente para Google Places API (New)."""

    BASE_URL = "https://places.googleapis.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search_attractions(
        self,
        destination: str,
        interests: list[str],
        budget_per_day: float,
    ) -> list[dict]:
        """Text Search por atracoes, restaurantes, pontos turisticos.

        Para cada interesse, faz uma busca:
        - "museums in Paris"
        - "restaurants in Paris"
        - "outdoor activities in Paris"

        Retorna atividades normalizadas com: name, address, coordinates,
        rating, photos, opening_hours, price_level, place_id.
        """

    async def get_place_details(self, place_id: str) -> dict:
        """Detalhes completos com reviews, fotos HD, telefone."""

    async def get_place_photo_url(
        self, photo_name: str, max_width: int = 800
    ) -> str:
        """Retorna URL da foto do lugar."""

    def _map_category(self, google_types: list[str]) -> str:
        """Mapeia tipos do Google Places para categorias do sistema."""
```

**Mapeamento de categorias:**
```python
GOOGLE_TYPE_TO_CATEGORY = {
    "museum": "culture",
    "art_gallery": "culture",
    "restaurant": "gastronomy",
    "cafe": "gastronomy",
    "park": "nature",
    "tourist_attraction": "sightseeing",
    "shopping_mall": "shopping",
    "night_club": "nightlife",
    "church": "culture",
    "beach": "nature",
    "amusement_park": "entertainment",
    "spa": "wellness",
}
```

**Fallback chain:**
```
Google Places API → Mock Provider (existente)
```

**Campos novos em `Activity` (models.py):**
```python
photos: list[str] = []           # URLs das fotos (Google Places)
rating: float | None = None      # Rating do Google (1.0-5.0)
review_count: int | None = None  # Numero de reviews
place_id: str | None = None      # Google Place ID
```

**Esforco**: 5h

---

### Tarefa 1.4: Maps — Google Maps API (Geocoding + Directions)

**Motivo**: O sistema atual usa coordenadas dos mocks e Haversine para distancias. Com Google Maps, teremos geocoding real, rotas otimizadas, tempo de viagem real, e distance matrix.

**Endpoints a usar:**

| Endpoint | Uso |
|----------|-----|
| `maps.googleapis.com/maps/api/geocode/json` | Geocoding (nome → coords) |
| `maps.googleapis.com/maps/api/directions/json` | Rota entre pontos (polyline, duracao, distancia) |
| `maps.googleapis.com/maps/api/distancematrix/json` | Matriz de distancias N×M |

**Arquivos criados:**
- `src/travel_orchestrator/mcp_servers/maps/__init__.py`
- `src/travel_orchestrator/mcp_servers/maps/server.py`
- `src/travel_orchestrator/mcp_servers/maps/client.py`
- `src/travel_orchestrator/mcp_servers/maps/google_maps_provider.py`
- `src/travel_orchestrator/mcp_servers/maps/mock_provider.py`
- `tests/unit/mcp_servers/test_maps.py`

**Tools MCP expostas:**

| Tool | Input | Output |
|------|-------|--------|
| `geocode` | address | `{lat, lng, formatted_address}` |
| `get_directions` | origin, destination, mode | `{distance_km, duration_min, polyline, steps}` |
| `get_distance_matrix` | origins[], destinations[] | Matriz `{distance_km, duration_min}` |
| `optimize_route` | waypoints[] | Ordem otimizada + rotas entre pontos |

**Implementacao `google_maps_provider.py`:**

```python
class GoogleMapsProvider:
    """Cliente para Google Maps Platform APIs."""

    async def geocode(self, address: str) -> dict:
        """Geocoding: nome/endereco → lat, lng, formatted_address."""

    async def get_directions(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> dict:
        """Rota entre dois pontos. Retorna polyline encoded, duracao, distancia."""

    async def get_distance_matrix(
        self, origins: list[str], destinations: list[str], mode: str = "walking"
    ) -> list[list[dict]]:
        """Matriz N×M de distancias/duracoes."""

    async def optimize_route(
        self, waypoints: list[dict], mode: str = "walking"
    ) -> dict:
        """Reordena waypoints para rota otimizada (TSP simplificado)."""
```

**Integracao com `optimize_itinerary.py`:**
- Substituir Haversine por `get_distance_matrix` para calculo real de tempo de deslocamento
- Usar `optimize_route` como input para o deterministic fallback
- Polylines retornadas sao armazenadas no state para renderizacao no mapa

**Campos novos no state:**
```python
class ItineraryDay(TypedDict):
    # ... existentes ...
    route_polylines: list[str]  # NOVO: encoded polylines para o mapa
    total_travel_minutes: int   # NOVO: tempo real de deslocamento no dia
```

**Fallback chain:**
```
Google Maps API → Haversine (calculo existente)
```

**Esforco**: 5h

---

### Tarefa 1.5: Testes de integracao para MCPs reais

**Arquivos criados:**
- `tests/integration/test_open_meteo.py`
- `tests/integration/test_booking_provider.py`
- `tests/integration/test_google_places.py`
- `tests/integration/test_google_maps.py`

**Estrategia**: Testes marcados com `@pytest.mark.integration` e `@pytest.mark.skipif(not API_KEY)`. CI roda apenas unit tests; integracao roda manualmente ou em pipeline separado.

**Esforco**: 2h

---

**Esforco total Fase 1: ~21h (~4-5 dias)**

---

## 5. Fase 2 — Frontend React Premium

### Tarefa 2.1: Scaffold Vite + React + TypeScript

**Estrutura do projeto frontend:**

```
frontend/                              # Raiz do frontend React (nova pasta na raiz do repo)
  package.json
  tsconfig.json
  vite.config.ts
  tailwind.config.ts
  postcss.config.js
  index.html
  public/
    favicon.ico
  src/
    main.tsx
    App.tsx
    api/
      client.ts                        # Axios/fetch wrapper para /api/*
      websocket.ts                     # Hook para WebSocket
      types.ts                         # Tipos TypeScript do state
    components/
      layout/
        Header.tsx
        Sidebar.tsx
        TabBar.tsx
      planning/
        TripForm.tsx                    # Formulario de planejamento
        FileUpload.tsx                 # Upload de arquivos (audio, imagem, PDF)
        PlanningProgress.tsx           # Barra de progresso com WebSocket
      results/
        PlanSummary.tsx                # Card resumo do plano
        HotelCard.tsx                  # Card do hotel com foto
        ActivityCard.tsx               # Card de atividade com foto
        RiskFlags.tsx                  # Alertas e risk flags
      itinerary/
        Timeline.tsx                   # Timeline visual dia-a-dia
        DayCard.tsx                    # Card de um dia
        ActivitySlot.tsx               # Slot de atividade na timeline
        DragDropContext.tsx            # Wrapper drag-and-drop
      map/
        MapView.tsx                    # Mapa Mapbox GL JS
        MapMarker.tsx                  # Marker customizado
        RouteLayer.tsx                 # Camada de rota
        WeatherOverlay.tsx             # Overlay de clima por dia
        PhotoPopup.tsx                 # Popup com foto do lugar
      dashboard/
        WeatherPanel.tsx               # Painel de clima
        BudgetPanel.tsx                # Painel de custos
        AgendaPanel.tsx                # Agenda compacta
      review/
        ApprovalPanel.tsx              # Painel de aprovacao
      observability/
        GraphPanel.tsx                 # Grafo LangGraph em tempo real
        NodeStatus.tsx                 # Status de um node
        EventLog.tsx                   # Log de eventos/decisoes
        LatencyChart.tsx               # Grafico de latencia por step
    hooks/
      usePlanningWebSocket.ts          # Hook WebSocket
      usePlanState.ts                  # Estado do plano (React Query ou Zustand)
      useMapInteraction.ts             # Interacao com o mapa
    utils/
      formatters.ts                    # Formatacao de moeda, datas
      constants.ts                     # Constantes do frontend
    styles/
      globals.css                      # Tailwind base
```

**Arquivos modificados no backend:**
- `docker-compose.yml` — servir build do React como volume ou multi-stage build
- `Dockerfile` — multi-stage build (Node + Python)
- `src/travel_orchestrator/frontend/server.py` — servir `frontend/dist/` como static

**Esforco**: 3h

---

### Tarefa 2.2: Mapa interativo (Mapbox GL JS)

**Por que Mapbox GL JS em vez de Leaflet:**
- Rendering WebGL (suave com muitos markers)
- Estilizacao nativa de camadas (weather overlay, rotas)
- Navegacao 3D (pitch/bearing para apresentacao)
- Free tier: 50k loads/mes

**Componente `MapView.tsx`:**

```typescript
interface MapViewProps {
  hotel: HotelOption | null;
  activities: Activity[];
  itinerary: OptimizedItinerary | null;
  selectedDay: number | null;      // Filtra markers/rotas por dia
  weatherByDay: WeatherForecast[]; // Overlay de clima
  onActivityClick: (id: string) => void;
}
```

**Funcionalidades:**
1. **Hotel marker** (vermelho, icone casa) — centralizado
2. **Activity markers** (coloridos por dia) — com popup contendo foto real (Google Places)
3. **Rota dia-a-dia** — polyline entre hotel → atividades → hotel, usando encoded polylines do Google Directions
4. **Filtro por dia** — sidebar seleciona dia e mapa mostra apenas atividades/rota daquele dia
5. **Weather overlay** — icones de clima flutuando sobre o mapa por dia selecionado
6. **Photo popups** — clicar no marker mostra popup com foto, nome, rating, horario
7. **Fly-to animation** — transicao suave ao selecionar dia

**Arquivos criados:**
- `frontend/src/components/map/MapView.tsx`
- `frontend/src/components/map/MapMarker.tsx`
- `frontend/src/components/map/RouteLayer.tsx`
- `frontend/src/components/map/WeatherOverlay.tsx`
- `frontend/src/components/map/PhotoPopup.tsx`
- `frontend/src/hooks/useMapInteraction.ts`

**Dependencias npm:**
- `mapbox-gl` + `@types/mapbox-gl`
- `react-map-gl` (wrapper React para Mapbox)

**Esforco**: 6h

---

### Tarefa 2.3: Cards de atividades com imagens reais

**Componente `ActivityCard.tsx`:**

```typescript
interface ActivityCardProps {
  activity: Activity;
  photo?: string;         // URL da foto (Google Places)
  isSelected: boolean;
  onSelect: () => void;
  onMapFocus: () => void; // Zoom no mapa para esta atividade
}
```

**Layout do card:**
```
┌─────────────────────────────────┐
│  [FOTO DO LUGAR]                │  ← foto real do Google Places
│                                 │
├─────────────────────────────────┤
│  Musee d'Orsay          ★ 4.7  │  ← nome + rating
│  Culture · 120 min · €18       │  ← categoria + duracao + preco
│  09:00–18:00 (Tue closed)      │  ← horario
│                                 │
│  [Ver no mapa]   [Selecionar]  │  ← acoes
└─────────────────────────────────┘
```

**Arquivos criados:**
- `frontend/src/components/results/ActivityCard.tsx`
- `frontend/src/components/results/HotelCard.tsx`

**Esforco**: 2h

---

### Tarefa 2.4: Timeline visual com drag-and-drop

**Componente `Timeline.tsx`:**

```typescript
interface TimelineProps {
  itinerary: OptimizedItinerary;
  onReorder: (dayIndex: number, fromSlot: number, toSlot: number) => void;
  onDaySelect: (dayIndex: number) => void;
  selectedDay: number;
}
```

**Layout visual:**
```
Dia 1 · 15 Jan · "Cultural Discovery"      ☀️ 18°C
─────────────────────────────────────────────────
09:00 ──●── Musee du Louvre            3h · €17
         │   🚶 12 min walk
12:00 ──●── Cafe de Flore              1h · €25
         │   🚶 8 min walk
13:30 ──●── Musee d'Orsay              2h · €16
         │   🚶 15 min walk
16:00 ──●── Jardin du Luxembourg       1.5h · Free
─────────────────────────────────────────────────

Dia 2 · 16 Jan · "Gastronomic Tour"        🌧️ 12°C
─────────────────────────────────────────────────
09:00 ──●── Le Marais Food Tour        3h · €65
  ...
```

**Funcionalidades:**
1. **Drag-and-drop** entre slots do mesmo dia (reorder) — `@dnd-kit/core`
2. **Clique no slot** faz zoom no mapa para a atividade
3. **Tempo de deslocamento** entre atividades (do Google Directions)
4. **Icone de clima** por dia (do weather forecast)
5. **Indicador de conflito** se validadores detectarem problema (borda vermelha)

**Arquivos criados:**
- `frontend/src/components/itinerary/Timeline.tsx`
- `frontend/src/components/itinerary/DayCard.tsx`
- `frontend/src/components/itinerary/ActivitySlot.tsx`
- `frontend/src/components/itinerary/DragDropContext.tsx`

**Dependencias npm:**
- `@dnd-kit/core` + `@dnd-kit/sortable`

**Esforco**: 5h

---

### Tarefa 2.5: Dashboard integrado (clima + custos + agenda)

**Layout do dashboard (3 paineis laterais):**

```
┌───────────────────────────────────────────────────┐
│                    HEADER                          │
├──────────┬──────────┬──────────┬──────────────────┤
│ Weather  │ Budget   │ Agenda   │                  │
│ Panel    │ Panel    │ Panel    │                  │
│          │          │          │                  │
│ ☀️ 18°C  │ Budget:  │ Day 1:   │                  │
│ 🌧️ 12°C  │ $5,000   │ 4 acts   │   MAPA / TIMELINE│
│ ☁️ 15°C  │ Used:    │ Day 2:   │                  │
│          │ $3,200   │ 3 acts   │                  │
│ UV: 6    │ Left:    │ Day 3:   │                  │
│ AQI: 42  │ $1,800   │ 5 acts   │                  │
│          │          │          │                  │
│          │ [━━━━░░] │          │                  │
│          │  64%     │          │                  │
├──────────┴──────────┴──────────┤                  │
│        OBSERVABILITY           │                  │
│        (Fase 4)                │                  │
└────────────────────────────────┴──────────────────┘
```

**Arquivos criados:**
- `frontend/src/components/dashboard/WeatherPanel.tsx`
- `frontend/src/components/dashboard/BudgetPanel.tsx`
- `frontend/src/components/dashboard/AgendaPanel.tsx`

**Esforco**: 3h

---

### Tarefa 2.6: Formulario de planejamento + progress bar

**Substituir o HTML form atual por componentes React.**

**Componente `TripForm.tsx`:**
- Mesmos campos do HTML atual (destination, dates, budget, currency, group_size, interests)
- Uploads com preview (imagem, audio waveform simplificada, PDF icon)
- Validacao client-side (datas futuras, budget > 0, destination nao vazio)

**Componente `PlanningProgress.tsx`:**
- Conecta via WebSocket ao backend
- Mostra barra de progresso com etapa atual
- Lista de nodes executados com checkmarks
- Tempo decorrido

**Arquivos criados:**
- `frontend/src/components/planning/TripForm.tsx`
- `frontend/src/components/planning/FileUpload.tsx`
- `frontend/src/components/planning/PlanningProgress.tsx`

**Esforco**: 3h

---

### Tarefa 2.7: API client + tipos TypeScript

**Arquivos criados:**
- `frontend/src/api/client.ts` — wrapper fetch com base URL, error handling
- `frontend/src/api/websocket.ts` — hook WebSocket com reconnect
- `frontend/src/api/types.ts` — tipos TypeScript espelhando `state/models.py`

**Tipos principais:**
```typescript
interface TravelPlannerCore {
  plan_id: string;
  destination: string;
  dates: { start_date: string; end_date: string };
  budget: { total: number; currency: string; flexibility: number };
  traveler_profile: { interests: string[]; pace: string; group_size: number };
  hotel_options: HotelOption[];
  activity_options: Activity[];
  optimized_itinerary: OptimizedItinerary | null;
  current_cost: number;
  risk_flags: string[];
  // ...
}

interface Activity {
  id: string;
  name: string;
  category: string;
  coordinates: { lat: number; lng: number };
  photos: string[];        // URLs de fotos reais
  rating: number | null;
  // ...
}
```

**Esforco**: 2h

---

### Tarefa 2.8: Build pipeline e integracao Docker

**Modificar Dockerfile para multi-stage build:**

```dockerfile
# Stage 1: Build React
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.11-slim
WORKDIR /app
# ... (existente) ...
COPY --from=frontend-build /frontend/dist ./frontend-dist/
```

**Arquivos modificados:**
- `Dockerfile` — multi-stage build
- `docker-compose.yml` — remover volume mount do frontend, usar build
- `src/travel_orchestrator/frontend/server.py` — servir `frontend-dist/` em vez de `static/`

**Esforco**: 1.5h

---

**Esforco total Fase 2: ~25.5h (~5-6 dias)**

---

## 6. Fase 3 — Multimodalidade Visual

### Tarefa 3.1: Pins no mapa com fotos reais (Google Places Photos)

**Fluxo:**
1. `search_activities` node chama Google Places → retorna `photo_name` por atividade
2. Backend converte `photo_name` em URL proxy: `/api/places/photo/{photo_name}`
3. Frontend `PhotoPopup.tsx` exibe foto no popup do marker

**Endpoint proxy (evitar expor API key no frontend):**
```python
# server.py
@app.get("/api/places/photo/{photo_name}")
async def proxy_place_photo(photo_name: str, max_width: int = 800):
    """Proxy para Google Places Photos API."""
```

**Arquivos modificados:**
- `src/travel_orchestrator/frontend/server.py` — adicionar proxy endpoint
- `frontend/src/components/map/PhotoPopup.tsx` — ja criado na Tarefa 2.2

**Esforco**: 2h

---

### Tarefa 3.2: Overlay de clima no mapa por dia

**Componente `WeatherOverlay.tsx` (ja criado na Tarefa 2.2):**

**Funcionalidade:**
- Ao selecionar um dia na timeline, o mapa mostra:
  - Icone de clima flutuando no canto (sol, chuva, nublado)
  - Badge de temperatura
  - Se `rain_chance >= 60%`, fundo do mapa levemente azulado (hint visual)
  - Se `wind_speed >= 50`, indicador de vento

**Dados necessarios**: Ja disponiveis no `destination_analysis.forecast` do state.

**Esforco**: 2h

---

### Tarefa 3.3: Geracao de imagem para destinos sem foto

**Quando usar**: Atividades retornadas pelo mock provider (sem Google Places) ou quando `photos` esta vazio.

**Estrategia**: Usar a API de geracao de imagens para criar uma imagem representativa.

**Opcoes:**
1. **DALL-E 3 (OpenAI)** — `POST https://api.openai.com/v1/images/generations`
2. **Stable Diffusion (via API gratuita)** — alternativa sem custo

**Implementacao (modulo separado):**

**Arquivos criados:**
- `src/travel_orchestrator/multimodal/image_generator.py`

```python
class PlaceholderImageGenerator:
    """Gera imagens placeholder para atividades sem foto."""

    async def generate(
        self,
        activity_name: str,
        category: str,
        destination: str,
    ) -> str | None:
        """Retorna URL/path da imagem gerada, ou None se falhar."""

    def _build_prompt(self, name: str, category: str, dest: str) -> str:
        """Ex: 'A scenic photo of Musee du Louvre in Paris, museum, daylight, travel photography'"""
```

**Fallback**: Se nenhuma API de imagem estiver configurada, usar placeholders SVG por categoria (ja existem os icones Unicode no PDF generator).

**Esforco**: 3h

---

### Tarefa 3.4: Input por voz (Web Speech API)

**Implementacao no frontend (sem backend):**

O navegador faz speech-to-text via Web Speech API e preenche os campos do formulario.

**Componente:**
```typescript
// frontend/src/components/planning/VoiceInput.tsx
interface VoiceInputProps {
  onTranscript: (text: string) => void;
  lang?: string; // "pt-BR" | "en-US"
}
```

**Funcionalidade:**
1. Botao de microfone no formulario
2. Web Speech API (`SpeechRecognition`) captura audio
3. Transcript e parseado para extrair: destino, datas, budget, interesses
4. Campos do formulario sao preenchidos automaticamente
5. Fallback: se Web Speech nao estiver disponivel, mostrar upload de arquivo audio (existente)

**Parsing do transcript (frontend):**
```typescript
function parseVoiceTranscript(text: string): Partial<TripFormData> {
  // Regex patterns para extrair:
  // - Destino: "quero ir para Paris" → destination = "Paris"
  // - Datas: "de 15 de janeiro a 22 de janeiro" → start/end_date
  // - Budget: "orcamento de 5 mil dolares" → budget = 5000, currency = "USD"
  // - Interesses: "gosto de museus e gastronomia" → interests = ["museums", "gastronomy"]
}
```

**Arquivos criados:**
- `frontend/src/components/planning/VoiceInput.tsx`
- `frontend/src/utils/voiceParser.ts`

**Esforco**: 3h

---

**Esforco total Fase 3: ~10h (~2-3 dias)**

---

## 7. Fase 4 — Observabilidade Visual para Apresentacao

### Tarefa 4.1: Instrumentar nodes para emitir eventos WebSocket

**Problema atual**: Os decorators `@track_node_execution` e `@track_planning` existem em `metrics.py` mas **nao sao aplicados nos nodes do grafo** (Gap G21 do ANALYSIS.md).

**Solucao**: Criar um decorator que emite eventos via WebSocket alem de registrar metricas Prometheus.

**Arquivos criados:**
- `src/travel_orchestrator/observability/event_emitter.py`

```python
class PlanningEventEmitter:
    """Emite eventos do pipeline para WebSocket + Prometheus."""

    def __init__(self, ws_manager: PlanningEventManager):
        self.ws_manager = ws_manager

    def track_node(self, node_name: str):
        """Decorator que emite node_start/node_end via WebSocket
        e registra metricas Prometheus."""

    def track_mcp_call(self, server_name: str, tool_name: str):
        """Decorator para chamadas MCP — emite mcp_call/mcp_result."""

    def track_validation(self, validator_name: str):
        """Decorator para validadores — emite validation events."""

    def track_llm_call(self, purpose: str):
        """Decorator para chamadas ao LLM — emite llm_call/llm_result."""
```

**Arquivos modificados:**
- `src/travel_orchestrator/graph/nodes/gather_requirements.py` — aplicar `@track_node`
- `src/travel_orchestrator/graph/nodes/analyze_destination.py` — aplicar `@track_node`
- `src/travel_orchestrator/graph/nodes/search_hotels.py` — aplicar `@track_node` + `@track_mcp_call`
- `src/travel_orchestrator/graph/nodes/search_activities.py` — aplicar `@track_node` + `@track_mcp_call`
- `src/travel_orchestrator/graph/nodes/optimize_itinerary.py` — aplicar `@track_node` + `@track_validation` + `@track_llm_call`
- `src/travel_orchestrator/graph/nodes/calculate_budget.py` — aplicar `@track_node` + `@track_validation`
- `src/travel_orchestrator/graph/nodes/risk_check.py` — aplicar `@track_node`
- `src/travel_orchestrator/graph/nodes/present_for_approval.py` — aplicar `@track_node`
- `src/travel_orchestrator/mcp_servers/hotels/client.py` — aplicar `@track_mcp_call`
- `src/travel_orchestrator/mcp_servers/weather/client.py` — aplicar `@track_mcp_call`
- `src/travel_orchestrator/mcp_servers/activities/client.py` — aplicar `@track_mcp_call`

**Esforco**: 3h

---

### Tarefa 4.2: Painel lateral — Grafo LangGraph em tempo real

**Componente `GraphPanel.tsx`:**

**Funcionalidade:**
- Renderiza o DAG do LangGraph como diagrama visual
- Cada node e um retangulo colorido por status:
  - Cinza: pendente
  - Azul pulsante: executando
  - Verde: completo
  - Vermelho: erro
- Edges sao setas entre nodes
- Atualiza em tempo real via WebSocket
- Mostra latencia em ms ao lado de cada node completo

**Layout visual:**
```
┌─────────────────────────────────┐
│  LangGraph Pipeline             │
│                                 │
│  ┌──────────────────┐           │
│  │ gather_requirements│ ✓ 120ms │
│  └────────┬─────────┘           │
│           │                     │
│  ┌────────▼─────────┐           │
│  │ analyze_destination│ ✓ 890ms │
│  └────────┬─────────┘           │
│           │                     │
│  ┌────────▼─────────┐           │
│  │ search_hotels     │ ⟳ ...   │  ← pulsando (executando)
│  └────────┬─────────┘           │
│           │                     │
│  ┌────────▼─────────┐           │
│  │ search_activities │ ○        │  ← pendente
│  └──────────────────┘           │
│  ...                            │
│                                 │
│  ─── MCP Calls ───              │
│  🔧 hotels.search_hotels  890ms│
│  🔧 weather.get_forecast  234ms│
│                                 │
│  ─── Decisions ───              │
│  ✓ Budget within limits         │
│  ⚠ High rain chance day 2       │
└─────────────────────────────────┘
```

**Tecnologia**: SVG renderizado com React (sem lib de grafos pesada para manter bundle leve).

**Arquivos criados:**
- `frontend/src/components/observability/GraphPanel.tsx`
- `frontend/src/components/observability/NodeStatus.tsx`
- `frontend/src/components/observability/GraphEdge.tsx`

**Esforco**: 5h

---

### Tarefa 4.3: Log de eventos e decisoes na UI

**Componente `EventLog.tsx`:**

```typescript
interface EventLogProps {
  events: PlanningEvent[];
  maxVisible?: number; // default 50
}

type PlanningEvent =
  | { type: "node_start"; node: string; timestamp: string }
  | { type: "node_end"; node: string; duration_ms: number; timestamp: string }
  | { type: "mcp_call"; server: string; tool: string; timestamp: string }
  | { type: "mcp_result"; server: string; tool: string; result_count: number }
  | { type: "validation"; validator: string; issues: ValidationIssue[] }
  | { type: "llm_call"; purpose: string; model: string; timestamp: string }
  | { type: "llm_result"; purpose: string; tokens: number; duration_ms: number }
  | { type: "decision"; description: string; outcome: string }
  | { type: "progress"; pct: number; message: string }
  | { type: "error"; message: string; node?: string }
  | { type: "complete"; plan_id: string };
```

**Layout:**
```
┌──────────────────────────────────────────┐
│ Event Log                          [Clear]│
├──────────────────────────────────────────┤
│ 14:32:01  ▶ gather_requirements started  │
│ 14:32:01  ✓ gather_requirements  120ms   │
│ 14:32:01  ▶ analyze_destination started  │
│ 14:32:02  🔧 weather.get_forecast called │
│ 14:32:02  🔧 weather.get_forecast → 7    │
│ 14:32:02  ✓ analyze_destination  890ms   │
│ 14:32:02  ▶ search_hotels started        │
│ 14:32:03  🔧 hotels.search_hotels called │
│ 14:32:04  🔧 hotels.search_hotels → 15   │
│ 14:32:04  ✓ search_hotels  1234ms        │
│ 14:32:04  ▶ optimize_itinerary started   │
│ 14:32:05  🤖 LLM call: itinerary opt     │
│ 14:32:08  🤖 LLM result: 1024 tokens 3s  │
│ 14:32:08  ⚠ validation: 2 timing issues  │
│ 14:32:08  🤖 LLM call: repair iteration  │
│ 14:32:10  ✓ optimize_itinerary  5890ms   │
│ ...                                      │
└──────────────────────────────────────────┘
```

**Arquivos criados:**
- `frontend/src/components/observability/EventLog.tsx`

**Esforco**: 2h

---

### Tarefa 4.4: Grafico de latencia por step

**Componente `LatencyChart.tsx`:**

Grafico de barras horizontal mostrando duracao de cada node/step apos o pipeline completar.

```
gather_requirements  ━━ 120ms
analyze_destination  ━━━━━━━━ 890ms
search_hotels        ━━━━━━━━━━━━━ 1234ms
search_activities    ━━━━━━━ 780ms
optimize_itinerary   ━━━━━━━━━━━━━━━━━━━━━━━━━━ 5890ms
calculate_budget     ━━ 45ms
risk_check           ━━ 89ms
present_for_approval ━ 12ms
─────────────────────────────────────────────────
Total pipeline: 9060ms
```

**Tecnologia**: CSS bars (sem lib de charts).

**Arquivos criados:**
- `frontend/src/components/observability/LatencyChart.tsx`

**Esforco**: 1.5h

---

### Tarefa 4.5: Hook WebSocket para observabilidade

**`usePlanningWebSocket.ts`:**

```typescript
function usePlanningWebSocket(planId: string | null) {
  const [events, setEvents] = useState<PlanningEvent[]>([]);
  const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>({});
  const [isConnected, setIsConnected] = useState(false);

  // Conecta ao ws://host:7860/ws/plan/{planId}
  // Recebe eventos JSON do backend
  // Atualiza estado reativo dos nodes

  return { events, nodeStates, isConnected };
}
```

**Arquivos criados:**
- `frontend/src/hooks/usePlanningWebSocket.ts`

**Esforco**: 1.5h

---

**Esforco total Fase 4: ~13h (~2.5-3 dias)**

---

## 8. Dependencias entre Tarefas

```
Tarefa 0.1 (Settings) ─────────────────┬──→ Tarefa 1.1 (Open-Meteo)
                                        ├──→ Tarefa 1.2 (Booking)
                                        ├──→ Tarefa 1.3 (Google Places)
                                        └──→ Tarefa 1.4 (Google Maps)

Tarefa 0.2 (flight_options state) ─────→ Tarefa 1.4 (Google Maps — route optimization)

Tarefa 0.3 (WebSocket) ────────────────┬──→ Tarefa 2.6 (PlanningProgress)
                                        └──→ Tarefa 4.1 (Event Emitter)

Tarefa 0.4 (CORS) ─────────────────────→ Tarefa 2.1 (React scaffold — precisa CORS para dev)

Tarefa 0.5 (Redis state) ──────────────→ Tarefa 2.6 (TripForm — session-based state)

Tarefa 1.1 (Open-Meteo) ──────────────→ Tarefa 3.2 (Weather overlay no mapa)

Tarefa 1.2 (Booking) ─────────────────→ Tarefa 2.3 (HotelCard com foto real)

Tarefa 1.3 (Google Places) ────────────┬──→ Tarefa 2.3 (ActivityCard com foto real)
                                        ├──→ Tarefa 3.1 (Pins com fotos no mapa)
                                        └──→ Tarefa 3.3 (Image generation fallback)

Tarefa 1.4 (Google Maps) ─────────────┬──→ Tarefa 2.2 (RouteLayer com polylines reais)
                                        └──→ Tarefa 2.4 (Timeline com tempo de deslocamento real)

Tarefa 2.1 (React scaffold) ──────────┬──→ Tarefa 2.2 (MapView)
                                        ├──→ Tarefa 2.3 (Cards)
                                        ├──→ Tarefa 2.4 (Timeline)
                                        ├──→ Tarefa 2.5 (Dashboard)
                                        ├──→ Tarefa 2.6 (TripForm)
                                        └──→ Tarefa 2.7 (API client)

Tarefa 2.1 (React scaffold) ──────────→ Tarefa 4.2 (GraphPanel)
                                        → Tarefa 4.3 (EventLog)
                                        → Tarefa 4.4 (LatencyChart)

Tarefa 2.8 (Docker build) ─────────────→ Deploy final

Tarefa 4.1 (Event Emitter) ───────────→ Tarefa 4.2 (GraphPanel — consome eventos)
                                        → Tarefa 4.3 (EventLog — consome eventos)
                                        → Tarefa 4.4 (LatencyChart — consome eventos)

Tarefa 4.5 (WS Hook) ─────────────────→ Tarefa 4.2 (GraphPanel)
                                        → Tarefa 4.3 (EventLog)
```

### Caminho critico

```
0.1 → 1.3 → 3.1 → (apresentacao)
0.3 → 4.1 → 4.2 → (apresentacao)
0.4 → 2.1 → 2.2 → 2.4 → (apresentacao)
```

### Ordem de implementacao recomendada

| Ordem | Tarefa | Depende de | Esforco |
|-------|--------|------------|---------|
| 1 | 0.1 Settings | — | 0.5h |
| 2 | 0.2 flight_options | — | 0.25h |
| 3 | 0.4 CORS | — | 0.25h |
| 4 | 0.3 WebSocket | — | 1h |
| 5 | 0.5 Redis state | — | 1.5h |
| 6 | 1.1 Open-Meteo | 0.1 | 4h |
| 7 | 1.3 Google Places | 0.1 | 5h |
| 8 | 1.4 Google Maps | 0.1, 0.2 | 5h |
| 9 | 1.2 Booking | 0.1 | 5h |
| 10 | 2.1 React scaffold | 0.4 | 3h |
| 11 | 2.7 API client + types | 2.1 | 2h |
| 12 | 2.6 TripForm + progress | 2.1, 0.3, 0.5 | 3h |
| 13 | 2.2 MapView (Mapbox) | 2.1, 1.4 | 6h |
| 14 | 2.3 Cards (hotel + activity) | 2.1, 1.2, 1.3 | 2h |
| 15 | 2.4 Timeline drag-drop | 2.1, 1.4 | 5h |
| 16 | 2.5 Dashboard panels | 2.1, 1.1 | 3h |
| 17 | 4.1 Event Emitter | 0.3 | 3h |
| 18 | 4.5 WS Hook | 2.1, 0.3 | 1.5h |
| 19 | 4.2 GraphPanel | 2.1, 4.1, 4.5 | 5h |
| 20 | 4.3 EventLog | 2.1, 4.1, 4.5 | 2h |
| 21 | 4.4 LatencyChart | 2.1, 4.1 | 1.5h |
| 22 | 3.1 Pins com fotos | 2.2, 1.3 | 2h |
| 23 | 3.2 Weather overlay | 2.2, 1.1 | 2h |
| 24 | 3.3 Image generation | 1.3 | 3h |
| 25 | 3.4 Voice input | 2.6 | 3h |
| 26 | 1.5 Integration tests | 1.1-1.4 | 2h |
| 27 | 2.8 Docker multi-stage | 2.1-2.7 | 1.5h |

---

## 9. Novas Dependencias (pyproject.toml)

### Producao

| Pacote | Versao | Uso | Fase |
|--------|--------|-----|------|
| `redis[hiredis]` | `>=5.0` | State store (ja provisionado) | 0 |
| `websockets` | `>=12.0` | WebSocket no FastAPI (nativo, mas boa pratica listar) | 0 |

### Frontend (package.json — nova)

| Pacote | Versao | Uso | Fase |
|--------|--------|-----|------|
| `react` | `^18` | Framework UI | 2 |
| `react-dom` | `^18` | React DOM | 2 |
| `typescript` | `^5` | Type safety | 2 |
| `vite` | `^5` | Build tool | 2 |
| `@vitejs/plugin-react` | `^4` | React plugin Vite | 2 |
| `tailwindcss` | `^3` | CSS utility | 2 |
| `postcss` | `^8` | CSS processing | 2 |
| `autoprefixer` | `^10` | CSS prefixing | 2 |
| `mapbox-gl` | `^3` | Mapa interativo | 2 |
| `react-map-gl` | `^7` | React wrapper Mapbox | 2 |
| `@dnd-kit/core` | `^6` | Drag and drop | 2 |
| `@dnd-kit/sortable` | `^8` | Sortable lists | 2 |
| `zustand` | `^4` | State management | 2 |

---

## 10. Novas Variaveis de Ambiente

```env
# .env (adicionar ao .env.example)

# === Fase 0 ===
MAPBOX_ACCESS_TOKEN=pk.xxx           # Mapbox GL JS (free tier: 50k loads/mes)
WS_ENABLED=true                      # Habilitar WebSocket

# === Fase 1 ===
# Weather: Open-Meteo nao precisa de key!

# Hotels
RAPIDAPI_KEY=xxx                     # RapidAPI key para Booking.com
SERPAPI_KEY=xxx                       # SerpAPI (fallback)

# Google
GOOGLE_MAPS_API_KEY=xxx              # Google Maps Platform (Geocoding + Directions + Distance Matrix)
GOOGLE_PLACES_API_KEY=xxx            # Google Places API (pode ser o mesmo key do Maps)
```

---

## 11. Inventario de Arquivos

### Arquivos novos a criar

| Fase | Arquivo | Tipo | Descricao |
|------|---------|------|-----------|
| 0 | `src/.../frontend/ws_manager.py` | Python | WebSocket connection manager |
| 0 | `src/.../frontend/state_store.py` | Python | Redis state store |
| 1 | `src/.../mcp_servers/weather/open_meteo_provider.py` | Python | Open-Meteo API client |
| 1 | `src/.../mcp_servers/hotels/booking_provider.py` | Python | Booking.com RapidAPI client |
| 1 | `src/.../mcp_servers/activities/google_places_provider.py` | Python | Google Places API client |
| 1 | `src/.../mcp_servers/maps/__init__.py` | Python | Maps MCP module init |
| 1 | `src/.../mcp_servers/maps/server.py` | Python | Maps MCP server |
| 1 | `src/.../mcp_servers/maps/client.py` | Python | Maps MCP client |
| 1 | `src/.../mcp_servers/maps/google_maps_provider.py` | Python | Google Maps API client |
| 1 | `src/.../mcp_servers/maps/mock_provider.py` | Python | Maps mock provider |
| 1 | `tests/integration/test_open_meteo.py` | Python | Open-Meteo integration tests |
| 1 | `tests/integration/test_booking_provider.py` | Python | Booking integration tests |
| 1 | `tests/integration/test_google_places.py` | Python | Google Places integration tests |
| 1 | `tests/integration/test_google_maps.py` | Python | Google Maps integration tests |
| 1 | `tests/unit/mcp_servers/test_maps.py` | Python | Maps unit tests |
| 2 | `frontend/` (inteira) | React/TS | ~40 arquivos (ver Tarefa 2.1) |
| 3 | `src/.../multimodal/image_generator.py` | Python | Image generation (DALL-E / placeholder) |
| 3 | `frontend/src/components/planning/VoiceInput.tsx` | React | Web Speech API input |
| 3 | `frontend/src/utils/voiceParser.ts` | TypeScript | Voice transcript parser |
| 4 | `src/.../observability/event_emitter.py` | Python | WebSocket event emitter + Prometheus |

**Total de novos arquivos Python**: ~16
**Total de novos arquivos React/TS**: ~40
**Total**: ~56 novos arquivos

### Arquivos existentes a modificar

| Fase | Arquivo | Mudanca |
|------|---------|---------|
| 0 | `src/.../config/settings.py` | Adicionar campos de API keys |
| 0 | `src/.../state/models.py` | Adicionar `flight_options`, campos em `Activity`, `HotelOption`, `ItineraryDay` |
| 0 | `src/.../frontend/server.py` | WebSocket endpoint, CORS, proxy photos, servir React build |
| 0 | `src/.../frontend/app.py` | Remover `_last_result_state`, usar state_store |
| 1 | `src/.../mcp_servers/weather/server.py` | Dispatch para Open-Meteo |
| 1 | `src/.../mcp_servers/weather/client.py` | Nova tool `get_air_quality` |
| 1 | `src/.../mcp_servers/hotels/server.py` | Dispatch para Booking |
| 1 | `src/.../mcp_servers/hotels/models.py` | Campos `photos`, `booking_url` |
| 1 | `src/.../mcp_servers/activities/server.py` | Dispatch para Google Places |
| 1 | `src/.../mcp_servers/activities/client.py` | Nova funcao `get_place_photo` |
| 1 | `tests/unit/mcp_servers/test_weather.py` | Testes Open-Meteo |
| 1 | `tests/unit/mcp_servers/test_hotels.py` | Testes Booking |
| 1 | `tests/unit/mcp_servers/test_activities.py` | Testes Google Places |
| 2 | `Dockerfile` | Multi-stage build (Node + Python) |
| 2 | `docker-compose.yml` | Ajustar build context |
| 4 | `src/.../graph/nodes/gather_requirements.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/analyze_destination.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/search_hotels.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/search_activities.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/optimize_itinerary.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/calculate_budget.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/risk_check.py` | Aplicar decorators de evento |
| 4 | `src/.../graph/nodes/present_for_approval.py` | Aplicar decorators de evento |
| 4 | `src/.../mcp_servers/hotels/client.py` | Aplicar `@track_mcp_call` |
| 4 | `src/.../mcp_servers/weather/client.py` | Aplicar `@track_mcp_call` |
| 4 | `src/.../mcp_servers/activities/client.py` | Aplicar `@track_mcp_call` |

**Total de arquivos modificados**: ~26

---

## 12. Riscos e Mitigacoes

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Google Places API custo alto | Media | Alto | Implementar cache agressivo (Redis, TTL 24h); limitar fotos a 3 por atividade; usar mock em dev |
| RapidAPI Booking rate limit | Media | Medio | Usar SerpAPI como fallback; cache de resultados por destino+datas (TTL 1h) |
| Open-Meteo downtime | Baixa | Baixo | Fallback para mock provider (ja implementado no pattern existente) |
| Mapbox token exposto no frontend | Alta | Medio | Restringir token por dominio no painel Mapbox; usar variavel de ambiente |
| WebSocket connection drops | Media | Baixo | Reconnect automatico no hook React; buffering de eventos perdidos |
| Bundle React muito grande | Media | Medio | Code splitting por rota; lazy loading do Mapbox; tree shaking |
| Google Maps API custo em escala | Baixa (demo) | Alto (prod) | Para demo: $200 free credit; para prod: implementar cache + proxy |
| Web Speech API nao disponivel | Media | Baixo | Fallback para upload de arquivo audio (funcionalidade existente) |

### Custos estimados de APIs (para demo/apresentacao)

| API | Free Tier | Custo alem do free |
|-----|-----------|-------------------|
| Open-Meteo | Ilimitado (gratuita) | — |
| RapidAPI Booking | 500 req/mes free | $0.01/req |
| Google Maps | $200/mes credito | $5/1000 req (Directions) |
| Google Places | $200/mes credito | $17/1000 req (Text Search) |
| Mapbox GL JS | 50k loads/mes free | $5/1000 loads |
| DALL-E 3 | — | $0.04/imagem (1024x1024) |

**Para uma demo/apresentacao**: Custo estimado $0-5 total (dentro dos free tiers).

---

## Apendice: Checklist de Apresentacao

Apos todas as fases implementadas, a demo deve ser capaz de:

- [ ] Usuario digita destino, datas, budget e interesses
- [ ] Painel de observabilidade mostra grafo executando em tempo real
- [ ] Log de eventos mostra cada node, MCP call, e decisao
- [ ] Mapa aparece com markers reais (fotos do Google Places)
- [ ] Timeline mostra roteiro dia-a-dia com drag-and-drop
- [ ] Cards de hotel e atividades mostram fotos reais
- [ ] Dashboard mostra clima real (Open-Meteo) + custos + agenda
- [ ] Weather overlay no mapa muda por dia
- [ ] Rotas reais (Google Directions) aparecem no mapa
- [ ] Latencia de cada step visivel no grafico
- [ ] Aprovacao/rejeicao do plano funciona
- [ ] Voice input preenche formulario
- [ ] PDF gerado com dados reais
