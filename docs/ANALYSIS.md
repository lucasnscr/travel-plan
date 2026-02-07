# Analise Completa do Travel Orchestrator

> Gerado em: 2026-02-06
> Versao do projeto: 0.1.0
> Commit base: `180b84f` (Initial commit)

---

## Sumario Executivo

O Travel Orchestrator e um sistema de planejamento de viagens com orquestracao multi-agente usando LangGraph, Anthropic Claude e MCP (Model Context Protocol). O projeto implementa um grafo de estados com 12 nodes, 3 edges condicionais, 4 MCP servers, 2 validadores deterministicos, pipeline multimodal (audio, imagem, PDF), geracao de documentos (PDF + mapa interativo), observabilidade (Prometheus + structlog) e frontend SPA (FastAPI + HTML estatico).

O sistema esta em estagio **alpha funcional**: a arquitetura central esta implementada e testada, mas varios nodes sao stubs, todos os MCP servers operam com mock providers por default, nao ha persistencia real, e o modulo `agents/` (A2A) esta vazio.

---

## 1. Arquitetura Atual: LangGraph

### 1.1 State Schema

O estado raiz do grafo e o TypedDict `TravelPlannerCore` (`state/models.py`), com 17 campos:

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `plan_id` | `str` | Identificador unico (`plan_<uuid8>`) |
| `destination` | `str` | Cidade/regiao destino |
| `dates` | `dict[str, str]` | `{start_date, end_date}` ISO 8601 |
| `budget` | `dict[str, float\|str]` | `{total, currency, flexibility}` |
| `traveler_profile` | `dict` | `{interests, pace, group_size}` |
| `selected_flight_id` | `Optional[str]` | ID do voo selecionado |
| `selected_hotel_id` | `Optional[str]` | ID do hotel selecionado |
| `selected_activity_ids` | `list[str]` | IDs das atividades selecionadas |
| `current_cost` | `float` | Custo total acumulado |
| `revision_count` | `int` | Contador de re-otimizacoes |
| `approval_status` | `Literal["pending","in_review","approved","rejected"]` | Status de aprovacao |
| `risk_flags` | `list[str]` | Alertas (budget, weather, policy, feedback) |
| `alternative_plans` | `dict[str, Any]` | Planos alternativos / competitor data |
| `destination_analysis` | `Optional[DestinationAnalysis]` | Clima, eventos, advisories |
| `hotel_options` | `list[HotelOption]` | Top 5 hoteis |
| `activity_options` | `list[Activity]` | 15-20 atividades |
| `optimized_itinerary` | `Optional[OptimizedItinerary]` | Agenda dia-a-dia |

### 1.2 TypedDicts Auxiliares

Definidos em `state/models.py`:

- **`FlightOption`**: id, airline, departure/arrival_time, duration_minutes, price, currency, stops, booking_class, carbon_footprint_kg, score
- **`HotelOption`**: id, name, address, coordinates, stars, price_per_night, currency, amenities, reviews_score, distance_to_center_km, score
- **`Activity`**: id, name, category, address, coordinates, duration_minutes, price, currency, opening_hours, requires_booking, indoor, description, score
- **`ItinerarySlot`**: activity_id, activity_name, start_time, end_time, travel_time_from_previous_minutes, notes
- **`ItineraryDay`**: date, day_number, theme, slots, weather_condition, notes
- **`OptimizedItinerary`**: days, unscheduled_activity_ids, optimization_method, validation_iterations, validation_warnings
- **`WeatherForecast`**: date, condition, temp_max, temp_min, rain_chance, rain_start, wind_speed
- **`WeatherSummary`**: avg_temp_max, avg_temp_min, avg_rain_chance, dominant_condition, severe_weather_days, packing_suggestions
- **`SeasonalEvent`**: name, category, description, month_start, month_end
- **`DestinationAnalysis`**: forecast, alerts, weather_summary, seasonal_events, travel_advisories, analysis_timestamp
- **`ValidationResult`**: is_valid, issues, severity, suggested_fixes
- **`TravelVibe`**: destination_suggestions, vibe_tags, budget_tier_guess, season_preference, activity_bias

### 1.3 Nodes (12 total)

Definidos em `graph/planner_graph.py`:

| # | Node | Arquivo | Status | Descricao |
|---|------|---------|--------|-----------|
| 1 | `gather_requirements` | `nodes/gather_requirements.py` | **Implementado** | Valida inputs, gera plan_id, enriquece perfil via Context MCP |
| 2 | `analyze_destination` | `nodes/analyze_destination.py` | **Implementado** | Weather forecast/alerts, eventos sazonais, weather summary, risk flags |
| 3 | `search_flights` | `planner_graph.py` (inline) | **STUB** | Retorna state inalterado. `# TODO: Implementar busca de voos` |
| 4 | `search_hotels` | `nodes/search_hotels.py` | **Implementado** | Aloca 35% budget, chama Hotels MCP, filtra/seleciona top 5 |
| 5 | `search_activities` | `nodes/search_activities.py` | **Implementado** | Aloca 20% budget, chama Activities MCP, balanceia indoor/outdoor |
| 6 | `optimize_itinerary` | `nodes/optimize_itinerary.py` | **Implementado** | Pipeline hibrido LLM + validators (max 3 iteracoes) + fallback deterministico |
| 7 | `calculate_budget` | `nodes/calculate_budget.py` | **Implementado** | Recalcula custos do zero, valida constraints, adiciona risk flags |
| 8 | `risk_and_policy_check` | `nodes/risk_check.py` | **Implementado** | Travel advisories (mock DB), approval threshold, restricoes, seguro |
| 9 | `present_for_approval` | `nodes/present_for_approval.py` | **Implementado** | HITL via `interrupt()`, monta apresentacao, processa decisao |
| 10 | `process_feedback` | `planner_graph.py` (inline) | **STUB** | Apenas incrementa `revision_count`. `# TODO: Implementar processamento de feedback` |
| 11 | `book_services` | `planner_graph.py` (inline) | **STUB** | Retorna state inalterado. `# TODO: Implementar reservas` |
| 12 | `generate_documents` | `planner_graph.py` (inline) | **STUB** | Retorna state inalterado. `# TODO: Implementar geracao de documentos` |

**Resumo**: 8/12 nodes implementados, 4 sao stubs (search_flights, process_feedback, book_services, generate_documents).

### 1.4 Edges

#### Edges Lineares

```
START -> gather_requirements -> analyze_destination -> search_flights
-> search_hotels -> search_activities -> optimize_itinerary -> calculate_budget
```

```
book_services -> generate_documents -> END
```

```
risk_and_policy_check -> present_for_approval
```

#### Edge Condicional 1: `should_optimize_costs` (apos `calculate_budget`)

**Arquivo**: `graph/edges.py:31`

```python
max_allowed = budget_total * (1 + max(flexibility, 0.10))  # teto = maior entre flex e 10%
if current_cost > max_allowed and revision_count < 3:
    return "optimize_costs"  # volta para search_flights
return "proceed"             # segue para risk_and_policy_check
```

- `"optimize_costs"` -> `search_flights` (loop de re-otimizacao)
- `"proceed"` -> `risk_and_policy_check`

#### Edge Condicional 2: `process_approval_decision` (apos `present_for_approval`)

**Arquivo**: `graph/edges.py:74`

```python
if state.get("approval_status") == "approved":
    return "approved"   # -> book_services
return "rejected"       # -> process_feedback
```

#### Edge Condicional 3: `determine_revision_target` (apos `process_feedback`)

**Arquivo**: `graph/edges.py:103`

Analisa keywords em `risk_flags` (PT + EN):

| Keywords | Destino |
|----------|---------|
| flight, voo, airline, aereo | `search_flights` |
| hotel, hospedagem, accommodation, alojamento | `search_hotels` |
| activity, atividade, itinerary, itinerario, passeio, tour, excursion, excursao | `search_activities` |
| (nenhum match) | `search_flights` (default) |

### 1.5 Diagrama do Grafo

```
START
  |
  v
gather_requirements
  |
  v
analyze_destination
  |
  v
search_flights (STUB)
  |
  v
search_hotels
  |
  v
search_activities
  |
  v
optimize_itinerary
  |
  v
calculate_budget
  |
  v
[should_optimize_costs]----+
  |                        |
  | "proceed"              | "optimize_costs" (max 3x)
  v                        v
risk_and_policy_check    search_flights (loop)
  |
  v
present_for_approval (HITL interrupt)
  |
  v
[process_approval_decision]
  |                    |
  | "approved"         | "rejected"
  v                    v
book_services (STUB)  process_feedback (STUB)
  |                    |
  v                    v
generate_documents   [determine_revision_target]
(STUB)                 |         |          |
  |                 flights   hotels   activities
  v                    |         |          |
 END               search_*   search_*   search_*
```

### 1.6 Checkpointing

- Usa `MemorySaver()` (in-memory) para checkpointing do LangGraph
- Configurado em `compile_graph()` (`planner_graph.py:168`)
- O node `present_for_approval` usa `interrupt()` do LangGraph para HITL
- Retomado via `Command(resume={"decision": "approved|rejected", "feedback": "..."})`

---

## 2. MCP Servers Implementados

### 2.1 Visao Geral

| MCP Server | Arquivo | Transport | Tools Expostas | Provider Real | Provider Mock |
|------------|---------|-----------|---------------|---------------|---------------|
| Hotels | `mcp_servers/hotels/server.py` | stdio | `search_hotels` | Enuygun (via Streamable HTTP) | `mock_provider.py` (6 cidades, ~40 hoteis) |
| Weather | `mcp_servers/weather/server.py` | stdio | `get_weather_forecast`, `get_weather_alerts` | OpenWeatherMap API | `mock_provider.py` (20 cidades, clima por latitude) |
| Activities | `mcp_servers/activities/server.py` | stdio | `discover_activities` | Nenhum | `mock_provider.py` (6 cidades, ~60 atividades, 8 eventos sazonais) |
| Context | `mcp_servers/context/preferences_server.py` | stdio | `set_user_preference`, `delete_user_preference`, `list_user_preferences` + 4 resource templates | Nenhum | `InMemoryStore` |

### 2.2 Hotels MCP Server (o mais completo)

**Arquitetura interna:**

```
client.py  -->  server.py  -->  enuygun_adapter.py (upstream real)
                      |
                      +--->  mock_provider.py (fallback)
                      |
                      +--->  models.py (HotelSearchInput, HotelResult, HotelLocation)
                      |
                      +--->  scoring.py (compute_scores: price 30%, location 25%, reviews 25%, amenities 20%)
                      |
                      +--->  retry.py (exponential backoff + jitter, max 3 retries)
```

**Tool `search_hotels`:**
- Input: destination, check_in, check_out, guests, preferences, location_centrality, min_stars, amenities
- Output: ate 15 hoteis normalizados e ranqueados
- Fallback automatico para mock se upstream falhar

**Enuygun Adapter** (`enuygun_adapter.py`):
- Conecta via `streamablehttp_client` do MCP SDK
- OAuth client credentials flow
- Discovery automatica de tool name via heuristica
- Semaphore de concorrencia (max 5 requests simultaneos)
- Retry com `RetryableError` para HTTP 429/5xx e erros de rede

**Mock Provider** (`mock_provider.py`):
- 6 cidades: Paris (8 hoteis), Tokyo (7), Rio de Janeiro (6), London (7), Lisbon (6), Sao Paulo (6)
- RNG seeded (deterministico): mesmo input -> mesmo output
- Jitter de preco +-10% para realismo
- Gera hoteis sinteticos para cidades desconhecidas

**Scoring** (`scoring.py`):
- `price_score` (30%): min-max normalizado, invertido (barato = melhor)
- `location_score` (25%): distancia ao centro, invertido
- `reviews_score` (25%): min-max normalizado
- `amenities_score` (20%): proporcao de amenities desejadas presentes

### 2.3 Weather MCP Server

**Tools expostas:**

| Tool | Input | Output |
|------|-------|--------|
| `get_weather_forecast` | destination, start_date, end_date | `list[WeatherForecast]` (1 por dia) |
| `get_weather_alerts` | destination | `list[{type, severity, message}]` |

**Provider real**: OpenWeatherMap One Call 3.0 API
- Geocoding: `/geo/1.0/direct` -> lat/lon
- Forecast: `/data/3.0/onecall` (8 dias diarios)
- Ativado quando `openweathermap_api_key` esta configurado (nota: campo nao existe em `Settings` — ver gaps)
- Fallback automatico para mock

**Mock Provider** (`mock_provider.py`):
- 20 cidades com coordenadas pre-definidas
- Classificacao climatica por latitude: tropical (<23.5), temperate (23.5-55), polar (>55)
- Cidades aridas por heuristica: Dubai, Cairo
- Condicoes por banda climatica (5 pools)
- RNG seeded por destino+data
- Alertas: 30% de chance de retornar 1 alerta (heat_wave, storm, flood)

### 2.4 Activities MCP Server

**Tool `discover_activities`:**
- Input: destination, interests, date_range, budget_per_day
- Output: ate 50 atividades filtradas e ranqueadas

**Mock Provider** (`mock_provider.py`) — o mais extenso:
- **6 cidades** com atividades curadas: Rio de Janeiro (13), Sao Paulo (10), Paris (10), Lisbon (9), Tokyo (9), London (8)
- **8 eventos sazonais**: Carnaval do Rio, Reveillon Copacabana, Festa Junina SP, 14 Juillet Paris, Marche de Noel Paris, Hanami Tokyo, Santo Antonio Lisbon, Winter Wonderland London
- **6 templates de horario**: museum, restaurant, tour, nature, shopping, nightlife
- **Scoring composto**: 40% base_score + 35% relevancia de interesses + 15% category match + 10% jitter
- **Diversidade**: cap por categoria (`max_results // 4`)
- **Clima-aware**: filtra atividades de praia se estacao fria
- `get_seasonal_events()`: funcao separada para o node `analyze_destination`

### 2.5 Context MCP Server (Preferences)

**Resources (URI scheme `preferences://`):**

| Resource Template | Descricao | Default |
|-------------------|-----------|---------|
| `preferences://user_{id}/travel_style` | Estilo e ritmo | `{style: "cultural", pace: "moderate"}` |
| `preferences://user_{id}/dietary_restrictions` | Restricoes alimentares | `[]` |
| `preferences://user_{id}/past_trips` | Viagens anteriores | `[]` |
| `preferences://user_{id}/accommodation_preferences` | Tipo e amenities | `{type: "hotel", amenities: ["wifi"]}` |

**Tools:**

| Tool | Descricao |
|------|-----------|
| `set_user_preference` | Upsert de preferencia |
| `delete_user_preference` | Reset para default |
| `list_user_preferences` | Lista todas com defaults |

**Backend**: `InMemoryStore` (dict Python)
- Interface abstrata `PreferenceBackend` definida para futura implementacao PostgreSQL/Redis
- Deep-copy em get/set para evitar mutacoes

### 2.6 Nota sobre Client Architecture

Todos os MCP clients (`hotels/client.py`, `weather/client.py`, `activities/client.py`, `context/client.py`) chamam diretamente as funcoes de implementacao do server no mesmo processo — **sem transport MCP real**. Cada client tem um comentario explicito:

> "When the system moves to a separate *-server process, swap this implementation for one that connects via `streamablehttp_client`."

Isso significa que o protocolo MCP esta definido (tools, schemas, handlers) mas **nao ha comunicacao MCP real entre processos**.

---

## 3. Agentes A2A

### 3.1 Status Atual

O modulo `agents/` (`src/travel_orchestrator/agents/__init__.py`) esta **vazio** — contem apenas o arquivo `__init__.py` sem conteudo.

### 3.2 Comunicacao Atual entre Componentes

Nao ha agentes A2A (Agent-to-Agent) implementados. A comunicacao entre nodes e feita exclusivamente via o state dict do LangGraph:

```
Node A -> escreve no state -> Node B le do state
```

Cada node recebe `TravelPlannerCore` e retorna `TravelPlannerCore` (spread + campos atualizados).

### 3.3 Pontos de Extensao para A2A

Os nodes atuais que poderiam ser convertidos em agentes autonomos:
- `search_flights` (stub): agente de pesquisa de voos
- `search_hotels`: agente de pesquisa de hospedagem
- `search_activities`: agente de atividades e experiencias
- `optimize_itinerary`: agente de otimizacao de roteiro
- `book_services` (stub): agente de reservas
- `process_feedback` (stub): agente de processamento de feedback

---

## 4. Validadores Deterministicos

### 4.1 ItineraryValidator (`validators/itinerary_validator.py`)

Classe estatica com 3 metodos de validacao:

#### `validate_geographic_coherence(activities, hotel, max_travel_time_minutes=90)`

- Calcula distancia total usando formula de Haversine: hotel -> atividade_1 -> atividade_2 -> ... -> hotel
- Velocidade urbana media: 30 km/h
- Limite default: 90 minutos de deslocamento por dia
- Retorna: `severity="error"` se exceder, com fix "Reagrupar atividades por proximidade geografica"

#### `validate_timing_conflicts(activities, date)`

Verifica:
- Numero de atividades > `MAX_ACTIVITIES_PER_DAY` (6)
- Duracao de atividade < `MIN_ACTIVITY_DURATION_MINUTES` (30 min)
- Atividade agendada em dia que esta fechada (verifica `opening_hours[weekday]`)
- Retorna: severity "error" para excesso/fechamento, "warning" para duracao

#### `validate_budget_constraints(state)`

- Erro se `current_cost > budget.total`
- Warning se margem < 10% (`current_cost > budget.total * 0.90`)
- Fixes: "Selecionar opcoes mais economicas de voo ou hotel"

### 4.2 WeatherValidator (`validators/weather_validator.py`)

Classe estatica com 2 metodos:

#### `validate_outdoor_activities(activities, forecast)`

Valida atividades outdoor contra previsao do dia:

| Condicao | Threshold | Severidade |
|----------|-----------|------------|
| Chance de chuva | >= 60% | warning |
| Vento perigoso | >= 50 km/h | error |
| Temperatura max extrema | >= 38 C | error |
| Temperatura min extrema | <= 0 C | error |

Fixes sugeridos: substituir por indoor, mover para dia com melhor previsao, agendar para manha/tarde.

#### `validate_weather_suitability(forecast)`

Check geral de adequacao:
- Condicoes severas: storm, thunderstorm, hurricane, typhoon
- Ventos >= 50 km/h
- Fix: "Considerar alterar datas da viagem se possivel"

### 4.3 Constantes de Validacao (`config/constants.py`)

| Constante | Valor | Uso |
|-----------|-------|-----|
| `MAX_DAILY_TRAVEL_TIME_MINUTES` | 90 | Geographic coherence |
| `MAX_ACTIVITIES_PER_DAY` | 6 | Timing conflicts |
| `MIN_ACTIVITY_DURATION_MINUTES` | 30 | Timing conflicts |
| `MAX_OPTIMIZATION_ITERATIONS` | 3 | LLM repair loop |
| `PACE_ACTIVITIES_PER_DAY` | fast=5, moderate=3, slow=2 | Itinerary optimization |
| `DEFAULT_DAY_START_HOUR` | "09:00" | Time slot assignment |
| `DEFAULT_DAY_END_HOUR` | "20:00" | Time slot assignment |
| `TRAVEL_BUFFER_MINUTES` | 15 | Buffer entre atividades |
| `RAIN_THRESHOLD_FOR_INDOOR` | 60.0% | Indoor preference trigger |
| `SUPPORTED_CURRENCIES` | USD, BRL, EUR | Currency validation |

### 4.4 Onde os Validadores Sao Usados

| Validador | Usado em | Momento |
|-----------|----------|---------|
| `ItineraryValidator.validate_geographic_coherence` | `optimize_itinerary` | Dentro do loop LLM repair |
| `ItineraryValidator.validate_timing_conflicts` | `optimize_itinerary` | Dentro do loop LLM repair |
| `ItineraryValidator.validate_budget_constraints` | `calculate_budget` | Apos reconciliacao de custos |
| `WeatherValidator.validate_outdoor_activities` | `optimize_itinerary` | Dentro do loop LLM repair |
| `WeatherValidator.validate_weather_suitability` | Nao usado diretamente | Disponivel mas nao integrado no grafo |

---

## 5. Modulos Adicionais

### 5.1 Multimodal (`multimodal/`)

Tres pipelines de input multimodal, todos com pattern identico: API real + mock fallback.

#### Audio Processor (`audio_processor.py`)

- **Transcricao**: OpenAI Whisper API (`whisper-1`) ou mock (3 transcricoes pre-definidas PT-BR)
- **Extracao**: Anthropic Claude extrai requirements estruturados ou mock keyword-based (PT+EN)
- **Output**: `AudioRequirements` TypedDict -> `TravelPlannerCore`-compatible state
- **Validacao**: formato (.mp3/.wav/etc), tamanho (max 25 MB)
- **Keywords mock**: 12 destinos, 12 meses PT, ~20 interesses, 6 pace keywords, group size patterns

#### Image Analyzer (`image_analyzer.py`)

- **Analise**: Anthropic Claude vision (base64 + prompt) ou mock (3 TravelVibes)
- **Output**: `TravelVibe` TypedDict (destination_suggestions, vibe_tags, budget_tier_guess, season_preference, activity_bias)
- **Validacao**: formato (.jpg/.jpeg/.png/.webp), tamanho (max 20 MB)

#### PDF Parser (`pdf_parser.py`)

- **Extracao**: Anthropic Claude document understanding (base64 PDF) ou mock (3 CompetitorOffers)
- **Output**: `CompetitorOffer` TypedDict (destination, price, currency, duration_days, highlights, hotel_name, raw_text)
- **Validacao**: formato (.pdf), tamanho (max 50 MB)

### 5.2 Output Generation (`output/`)

#### PDF Generator (`pdf_generator.py`)

Gera PDF estilizado A4 com ReportLab:
- **Capa**: titulo, destino, datas, plan_id
- **Sumario executivo**: tabela com destino, periodo, orcamento, custo total, variacao
- **Card do hotel**: nome, estrelas, endereco, preco/noite
- **Alertas**: risk flags com icone de warning
- **Itinerario dia-a-dia**: tabela por dia (horario, atividade, categoria, duracao, preco), placeholder de foto por categoria, notas do dia
- **Detalhamento de custos**: tabela itemizada (voos, hospedagem, atividades, total) + barra de variacao visual
- **Vouchers**: hotel voucher + activity vouchers para atividades com `requires_booking=True`
- **Design**: palette azul/laranja, tabelas estilizadas, icones Unicode de clima

#### Map Generator (`map_generator.py`)

Gera mapa HTML interativo com Folium:
- **Hotel**: marker vermelho com icone "home"
- **Atividades**: markers coloridos por dia (10 cores ciclicas)
- **Rotas**: PolyLine tracejada hotel -> atividades -> hotel por dia
- **Popups**: HTML com detalhes (nome, categoria, preco, duracao, descricao)
- **Controles**: LayerControl para toggle de dias
- **Tile**: OpenStreetMap
- **Zoom**: 13 (nivel urbano)

### 5.3 Observabilidade (`observability/`)

#### Metricas Prometheus (`metrics.py`)

| Metrica | Tipo | Labels | Descricao |
|---------|------|--------|-----------|
| `travel_plans_completed_total` | Counter | status | Planos completados (success/error) |
| `travel_plans_approved_total` | Counter | — | Planos aprovados |
| `travel_plans_rejected_total` | Counter | — | Planos rejeitados |
| `travel_planning_duration_seconds` | Histogram | — | Duracao do pipeline completo |
| `travel_plan_cost_dollars` | Histogram | — | Custo por plano |
| `travel_active_plannings` | Gauge | — | Planos em geracao simultanea |
| `travel_node_execution_seconds` | Histogram | node_name | Tempo de execucao por node |

**Decorators**:
- `@track_node_execution("node_name")`: mede tempo do node
- `@track_planning()`: mede pipeline completo (active gauge + duration + status)

**Test isolation**: `reset_metrics()` cria CollectorRegistry fresco para cada teste.

#### Server de Observabilidade (`observability/server.py`)

FastAPI app separado com:
- `GET /health` -> `{"status": "healthy"}`
- `GET /metrics` -> Prometheus exposition format
- `GET /dashboard` -> HTML estatico (nota: `dashboard.html` nao existe — ver gaps)

**Nota**: Esses endpoints estao duplicados no `frontend/server.py`, que e o servidor principal.

### 5.4 Frontend (`frontend/`)

#### Server (`server.py`)

FastAPI SPA servindo:
- `GET /` -> `static/index.html`
- `POST /api/plan` -> pipeline completo (multipart form com text + files)
- `POST /api/approve` -> aprovacao/rejeicao
- `GET /api/map/{filename}` -> mapas gerados
- `GET /api/pdf/{filename}` -> PDFs gerados
- `GET /health`, `GET /metrics`, `GET /dashboard` -> observabilidade

#### Business Logic (`app.py`)

Pipeline `plan_trip()`:
1. Processa inputs multimodal (audio, imagem, PDF)
2. Constroi initial state (merge text + multimodal)
3. Executa grafo LangGraph (`compile_graph().ainvoke()`)
4. Gera map HTML + PDF
5. Retorna (plan_json, map_html, pdf_path)

`handle_approval()`: atualiza `_last_result_state` em cache (dict global).

#### Entry Point (`__main__.py`)

```python
uvicorn.run("travel_orchestrator.frontend.server:app", host="0.0.0.0", port=7860)
```

### 5.5 Utils (`utils/`)

#### Logging (`logging.py`)

- structlog com JSON em producao, console colorido em dev
- `get_logger(name)` com auto-setup
- `add_context(**kwargs)` context manager com contextvars
- `@log_execution` decorator generico (entry + duration + outcome)
- `@log_node_execution("name")` decorator para nodes LangGraph (auto-bind plan_id)

### 5.6 Config (`config/`)

#### Settings (`settings.py`)

Singleton `Settings` via pydantic-settings:

| Campo | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| `anthropic_api_key` | str | **required** | Chave Anthropic |
| `openai_api_key` | str\|None | None | Whisper transcription |
| `langsmith_api_key` | str\|None | None | LangSmith tracing |
| `model_name` | str | `claude-sonnet-4-20250514` | Modelo Claude |
| `temperature` | float | 0.3 | Temperatura LLM |
| `max_tokens` | int | 4096 | Max tokens |
| `log_level` | str | INFO | Log level |
| `environment` | str | development | dev/staging/production |
| `max_budget_usd` | float | 50000.0 | Budget maximo absoluto |
| `approval_threshold_usd` | float | 10000.0 | Threshold de aprovacao |
| `max_retries` | int | 3 | Max retries para tool calls |
| `timeout_seconds` | int | 30 | Timeout padrao |
| `enuygun_mcp_url` | str | `https://mcp.enuygun.com/mcp` | Endpoint Enuygun |
| `enuygun_oauth_*` | str\|None | None | OAuth credentials |
| `redis_url` | str | `redis://localhost:6379/0` | Redis URL |
| `postgres_url` | str\|None | None | PostgreSQL URL |

---

## 6. Infraestrutura

### 6.1 Docker

**Dockerfile**:
- Base: `python:3.11-slim`
- Build: Poetry install (sem dev, sem virtualenv)
- Porta: 7860 (FastAPI unico)
- Healthcheck: `curl -f http://localhost:7860/health`
- Entrypoint: `scripts/entrypoint.sh` -> uvicorn

**docker-compose.yml** (3 services):

| Service | Imagem | Porta | Funcao |
|---------|--------|-------|--------|
| `app` | Build local | 7860 | FastAPI (SPA + API + metrics) |
| `redis` | redis:7-alpine | 6379 | Cache/state (nao utilizado pelo app ainda) |
| `prometheus` | prom/prometheus:latest | 9090 | Scraping de metricas |

**prometheus.yml**: scrape a cada 15s de `app:7860/metrics`

### 6.2 Volumes

- `app_data`: dados do app
- `redis_data`: persistencia Redis
- `prometheus_data`: dados Prometheus

---

## 7. Testes

### 7.1 Estrutura

```
tests/
  __init__.py
  unit/
    __init__.py
    test_analyze_destination.py
    test_audio_processor.py
    test_calculate_budget.py
    test_docker_config.py
    test_docs.py
    test_edges.py
    test_frontend_app.py
    test_gather_requirements.py
    test_image_analyzer.py
    test_map_generator.py
    test_metrics.py
    test_optimize_itinerary.py
    test_pdf_generator.py
    test_pdf_parser.py
    test_present_for_approval.py
    test_risk_check.py
    test_search_activities.py
    test_search_hotels.py
    test_validators.py
    mcp_servers/
      __init__.py
      test_activities.py
      test_context.py
      test_hotels.py
      test_weather.py
  integration/
    __init__.py
    test_map_generator_integration.py
```

### 7.2 Cobertura por Modulo

| Modulo | Arquivo de Teste | Status |
|--------|-----------------|--------|
| Nodes: gather_requirements | test_gather_requirements.py | Testado |
| Nodes: analyze_destination | test_analyze_destination.py | Testado |
| Nodes: search_hotels | test_search_hotels.py | Testado |
| Nodes: search_activities | test_search_activities.py | Testado |
| Nodes: optimize_itinerary | test_optimize_itinerary.py | Testado |
| Nodes: calculate_budget | test_calculate_budget.py | Testado |
| Nodes: risk_check | test_risk_check.py | Testado |
| Nodes: present_for_approval | test_present_for_approval.py | Testado |
| Edges | test_edges.py | Testado |
| Validators | test_validators.py | Testado |
| MCP: Hotels | mcp_servers/test_hotels.py | Testado |
| MCP: Weather | mcp_servers/test_weather.py | Testado |
| MCP: Activities | mcp_servers/test_activities.py | Testado |
| MCP: Context | mcp_servers/test_context.py | Testado |
| Multimodal: Audio | test_audio_processor.py | Testado |
| Multimodal: Image | test_image_analyzer.py | Testado |
| Multimodal: PDF | test_pdf_parser.py | Testado |
| Output: PDF | test_pdf_generator.py | Testado |
| Output: Map | test_map_generator.py | Testado |
| Observability: Metrics | test_metrics.py | Testado |
| Frontend: App | test_frontend_app.py | Testado |
| Docker/Docs | test_docker_config.py, test_docs.py | Testado |
| Integration: Map | test_map_generator_integration.py | Testado |

### 7.3 Configuracao

- `pytest` com `asyncio_mode = "auto"`
- Markers: `unit`, `integration`
- Filter warnings: `ignore::DeprecationWarning`

---

## 8. Gaps Identificados para Producao

### 8.1 Gaps Criticos

| # | Gap | Impacto | Onde |
|---|-----|---------|-----|
| G1 | **`search_flights` e um stub** | Nao ha busca de voos — custo de voo sempre 0 | `planner_graph.py:44-47` |
| G2 | **`book_services` e um stub** | Nenhuma reserva real acontece apos aprovacao | `planner_graph.py:58-60` |
| G3 | **`generate_documents` e um stub** | Node final nao gera nada (PDF/map sao gerados no frontend) | `planner_graph.py:64-67` |
| G4 | **`process_feedback` e um stub** | Apenas incrementa revision_count, nao processa feedback real | `planner_graph.py:51-54` |
| G5 | **Modulo `agents/` vazio** | Nenhum agente A2A implementado | `agents/__init__.py` |
| G6 | **Persistencia in-memory** | MemorySaver (LangGraph), InMemoryStore (context), dict global (frontend) — tudo perdido em restart | Multiplos |
| G7 | **MCP clients nao usam transport** | Chamadas diretas no mesmo processo, sem comunicacao MCP real | Todos os `client.py` |
| G8 | **`openweathermap_api_key` nao existe em Settings** | Weather server tenta ler `getattr(settings, "openweathermap_api_key", None)` mas campo nao esta definido em `Settings` | `weather/server.py:37-41` |

### 8.2 Gaps Importantes

| # | Gap | Impacto | Onde |
|---|-----|---------|-----|
| G9 | **Nao ha autenticacao/autorizacao** | Qualquer pessoa pode acessar a API e gerar planos | `frontend/server.py` |
| G10 | **Estado de aprovacao em variavel global** | `_last_result_state` e um dict global no modulo `app.py` — nao funciona com multiplos usuarios | `frontend/app.py:29` |
| G11 | **Nao ha rate limiting** | Sem protecao contra abuso da API | `frontend/server.py` |
| G12 | **`dashboard.html` nao existe** | Endpoint `/dashboard` vai crashar com FileNotFoundError | `frontend/server.py:34`, `observability/server.py:20` |
| G13 | **Redis provisionado mas nao usado** | docker-compose inclui Redis mas nenhum codigo o utiliza | `docker-compose.yml` |
| G14 | **Nao ha conversao de moedas** | Custos de hoteis/atividades em moeda local misturados com budget do viajante | Nodes de busca |
| G15 | **FlightOption TypedDict definido mas nao usado** | Modelo existe em `state/models.py` mas search_flights e um stub | `state/models.py:39-56` |
| G16 | **Nao ha testes end-to-end** | Nenhum teste executa o grafo completo | `tests/` |
| G17 | **`max_budget_usd` nao e validado nos nodes** | Campo existe em Settings mas nao ha validacao contra ele no grafo | `settings.py:35` |
| G18 | **Sem CORS configurado** | FastAPI sem middleware CORS — problematico se SPA for servida de dominio diferente | `frontend/server.py` |
| G19 | **Temp files nao sao limpos** | `_ARTIFACTS_DIR` e `tempfile.*` nunca sao limpos | `frontend/server.py`, `frontend/app.py` |
| G20 | **`flight_options` nao e campo formal do state** | `calculate_budget.py:106` faz `state.get("flight_options", [])` com `# type: ignore` | `calculate_budget.py` |

### 8.3 Gaps de Observabilidade

| # | Gap | Impacto |
|---|-----|---------|
| G21 | **Metricas nao sao registradas pelo grafo** | `@track_node_execution` e `@track_planning` existem mas nao sao aplicados nos nodes do grafo |
| G22 | **Sem distributed tracing** | LangSmith configurado em .env mas nao ativado no codigo |
| G23 | **Sem alerting** | Prometheus sem AlertManager |

### 8.4 Gaps de Seguranca

| # | Gap | Impacto |
|---|-----|---------|
| G24 | **API keys em env vars sem rotacao** | Sem vault/secrets management |
| G25 | **Uploads sem sanitizacao** | `_save_upload()` salva qualquer conteudo no filesystem |
| G26 | **Path traversal em serve_map/serve_pdf** | Filename vem da URL sem sanitizacao (parcialmente mitigado por `_ARTIFACTS_DIR`) |
| G27 | **Sem input validation na API** | Campos como `destination` e `budget` nao sao validados na API (apenas no node) |

---

## 9. Dependencias Atuais e Versoes

### 9.1 Dependencias de Producao

| Pacote | Versao Minima | Uso |
|--------|--------------|-----|
| `python` | ^3.11 | Runtime |
| `langgraph` | >=0.2.28 | Orquestracao de grafo de estados |
| `langchain-anthropic` | >=0.3.0 | Integracao LangChain + Claude |
| `anthropic` | >=0.39.0 | SDK Anthropic direto (optimize_itinerary, multimodal) |
| `mcp` | >=1.1.0 | Model Context Protocol SDK (servers + clients) |
| `pydantic` | >=2.0 | Validacao de modelos (hotels, settings) |
| `pydantic-settings` | >=2.0 | Configuracao via env vars |
| `structlog` | >=24.0 | Logging estruturado |
| `python-dotenv` | >=1.0 | Leitura de .env |
| `folium` | >=0.15 | Geracao de mapas interativos |
| `reportlab` | >=4.0 | Geracao de PDFs |
| `httpx` | >=0.27 | HTTP client async (Whisper API, OWM, Enuygun) |
| `python-multipart` | >=0.0.9 | Upload de arquivos no FastAPI |
| `prometheus-client` | >=0.20 | Metricas Prometheus |
| `fastapi` | >=0.115 | Framework web |
| `uvicorn` | >=0.32 | ASGI server |

### 9.2 Dependencias de Desenvolvimento

| Pacote | Versao Minima | Uso |
|--------|--------------|-----|
| `pytest` | >=8.0 | Test runner |
| `pytest-asyncio` | >=0.23 | Suporte a testes async |
| `ruff` | >=0.4.0 | Linter + formatter |
| `mypy` | >=1.10 | Type checking |

### 9.3 Dependencias Implicitas (nao declaradas mas usadas)

| Pacote | Usado em | Status |
|--------|----------|--------|
| `typing_extensions` | `state/models.py`, multimodal | Provavelmente transitiva via pydantic |

### 9.4 Build System

- **Package manager**: Poetry (`poetry.lock` presente)
- **Build backend**: `poetry.core.masonry.api`
- **Package layout**: src layout (`src/travel_orchestrator/`)
- **Target Python**: 3.11

---

## 10. Resumo de Maturidade por Modulo

| Modulo | Maturidade | Comentario |
|--------|-----------|------------|
| `state/models.py` | Alta | 12 TypedDicts bem definidos |
| `graph/planner_graph.py` | Media | Arquitetura completa mas 4 stubs |
| `graph/edges.py` | Alta | 3 routing functions completas e testadas |
| `graph/nodes/` (implementados) | Alta | 6 nodes funcionais com boa logica |
| `mcp_servers/hotels/` | Alta | Mais completo: upstream real, mock, scoring, retry, models |
| `mcp_servers/weather/` | Media | Live provider + mock, mas campo de config ausente |
| `mcp_servers/activities/` | Media-Alta | Mock extenso, nenhum provider real |
| `mcp_servers/context/` | Media | Funcional mas apenas in-memory |
| `validators/` | Alta | Deterministicos, bem testados |
| `multimodal/` | Media | 3 pipelines com pattern consistente, todos com mock fallback |
| `output/` | Alta | PDF estilizado + mapa interativo completos |
| `observability/` | Media | Metricas definidas mas nao integradas ao grafo |
| `frontend/` | Media | SPA funcional mas sem auth, state global |
| `agents/` | Inexistente | Modulo vazio |
| `config/` | Alta | Settings bem tipado com pydantic |
| `utils/logging` | Alta | structlog bem configurado com decorators |
| Testes | Alta | Cobertura ampla (unit + MCP + integracao parcial) |
| Docker | Media | Funcional mas sem multi-stage, sem non-root user |

---

## 11. Recomendacoes de Evolucao (Prioridade)

### P0 — Blockers para funcionalidade basica

1. Implementar `search_flights` node com MCP server de voos
2. Implementar `generate_documents` node (integrar PDF/map generators)
3. Corrigir `openweathermap_api_key` ausente no `Settings`
4. Adicionar `flight_options` como campo formal no `TravelPlannerCore`

### P1 — Necessarios para MVP

5. Implementar `process_feedback` com parsing real de feedback
6. Implementar `book_services` (mesmo que mock)
7. Migrar state de dict global para Redis (usando o Redis ja provisionado)
8. Criar `dashboard.html` ou remover endpoint
9. Adicionar autenticacao basica na API

### P2 — Importantes para producao

10. Implementar agentes A2A no modulo `agents/`
11. Migrar MCP clients para transport real (streamable HTTP)
12. Adicionar conversao de moedas
13. Implementar PreferenceBackend com PostgreSQL/Redis
14. Integrar metricas Prometheus nos nodes do grafo
15. Adicionar testes end-to-end do grafo completo
16. Configurar CORS, rate limiting, input validation na API
17. Limpar temp files com TTL
18. Adicionar LangSmith tracing
