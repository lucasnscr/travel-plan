# Arquitetura

## Grafo de Estados (LangGraph)

O sistema usa um `StateGraph` do LangGraph com 12 nodes e 3 edges condicionais.
O estado completo e definido pelo TypedDict `TravelPlannerCore` com 17 campos.

### Fluxo Completo

```
START
  |
  v
gather_requirements -----> Valida inputs, gera plan_id, enriquece perfil
  |
  v
analyze_destination -----> Weather forecast, alertas, eventos sazonais
  |
  v
search_flights ----------> (stub: retorna state inalterado)
  |
  v
search_hotels -----------> Busca via MCP, seleciona top 5, auto-seleciona melhor
  |
  v
search_activities -------> Busca via MCP, balanceia indoor/outdoor por clima
  |
  v
optimize_itinerary ------> LLM propoe agenda + validators corrigem (max 3 iteracoes)
  |
  v
calculate_budget --------> Reconcilia custos, valida budget constraints
  |
  v
[should_optimize_costs] --- condicional
  |           |
  | over      | within
  | budget    | budget
  v           v
search_    risk_and_policy_check --> Advisories, threshold, restricoes, seguro
flights       |
(loop         v
 max 3x)   present_for_approval --> HITL: interrupt() pausa execucao
              |
              v
         [process_approval_decision] --- condicional
              |             |
              | approved    | rejected
              v             v
         book_services   process_feedback --> Incrementa revision_count
         (stub)             |
              |             v
              |        [determine_revision_target] --- condicional
              |             |         |          |
              |          flights   hotels   activities
              |             |         |          |
              |             v         v          v
              |          search_   search_   search_
              |          flights   hotels    activities
              v
         generate_documents (stub)
              |
              v
            END
```

### Edges Condicionais

#### `should_optimize_costs(state)`

Chamado apos `calculate_budget`. Compara `current_cost` contra o teto:

```
teto = max(budget.total * (1 + flexibility), budget.total * 1.10)
```

- Se `current_cost > teto` E `revision_count < 3`: retorna `"optimize_costs"` (volta para `search_flights`)
- Caso contrario: retorna `"proceed"` (segue para `risk_and_policy_check`)

#### `process_approval_decision(state)`

Chamado apos `present_for_approval`:
- `approval_status == "approved"`: rota para `book_services`
- Caso contrario: rota para `process_feedback`

#### `determine_revision_target(state)`

Chamado apos `process_feedback`. Analisa feedback em `risk_flags` usando keyword matching (PT + EN):

| Keywords | Destino |
|----------|---------|
| flight, voo, airline, aereo | `search_flights` |
| hotel, hospedagem, accommodation, alojamento | `search_hotels` |
| activity, atividade, itinerary, itinerario, passeio, tour | `search_activities` |
| (nenhum match) | `search_flights` (default) |

## Nodes em Detalhe

### gather_requirements

**Arquivo**: `graph/nodes/gather_requirements.py`

- Valida campos obrigatorios: destination, dates, budget
- Gera `plan_id` unico (`plan_<uuid8>`)
- Busca preferencias do usuario via Context MCP Server
- Enriquece `traveler_profile` com preferencias salvas
- Inicializa campos mutaveis (risk_flags, revision_count, etc.)

### analyze_destination

**Arquivo**: `graph/nodes/analyze_destination.py`

- Chama Weather MCP: `get_weather_forecast()` + `get_weather_alerts()`
- Computa `WeatherSummary` (medias, condicao dominante, dias severos)
- Identifica eventos sazonais via Activities MCP
- Gera `packing_suggestions` baseado no clima
- Adiciona risk_flags para tempo severo

### search_hotels

**Arquivo**: `graph/nodes/search_hotels.py`

- Aloca 35% do budget total para hospedagem
- Chama Hotels MCP com filtros (budget, min_stars, amenities)
- Seleciona top 5 por score
- Auto-seleciona o melhor hotel
- Atualiza `current_cost`

### search_activities

**Arquivo**: `graph/nodes/search_activities.py`

- Aloca 20% do budget total para atividades
- Chama Activities MCP com interesses do perfil
- Balanceia indoor/outdoor baseado em `WeatherSummary`
- Garante diversidade de categorias
- Seleciona ~15 atividades
- Atualiza `current_cost`

### optimize_itinerary

**Arquivo**: `graph/nodes/optimize_itinerary.py`

Pipeline hibrido LLM + validacao deterministica:

1. **LLM propoe**: Claude gera agenda dia-a-dia com horarios
2. **Validators checam**:
   - `ItineraryValidator.validate_geographic_coherence()` — distancia hotel-atividades
   - `ItineraryValidator.validate_timing_conflicts()` — max 6 atividades/dia, duracao minima
   - `WeatherValidator.validate_outdoor_activities()` — chuva >= 60%, vento >= 50km/h
3. **LLM repara**: feedback dos validators e enviado ao Claude para correcao
4. **Loop**: max 3 iteracoes de validacao
5. **Fallback**: scheduling deterministico nearest-neighbor se LLM falhar

### calculate_budget

**Arquivo**: `graph/nodes/calculate_budget.py`

- Recalcula custo total do zero (voo + hotel + atividades)
- Executa `ItineraryValidator.validate_budget_constraints()`
- Adiciona risk_flags para estouros e margens apertadas (< 10%)

### risk_and_policy_check

**Arquivo**: `graph/nodes/risk_check.py`

- Nivel de advisory: RED (nao va) / ORANGE (reconsidere) / YELLOW (cuidado) / GREEN (ok)
- Flag custos acima do threshold de aprovacao ($10k default)
- Restricoes do destino: visa, saude, dress code, permissoes especiais
- Recomenda seguro: custo > $5k, duracao > 14 dias, advisory elevado

### present_for_approval

**Arquivo**: `graph/nodes/present_for_approval.py`

- Usa `langgraph.types.interrupt()` para pausar o grafo
- Monta apresentacao com resumo do plano, custos, riscos
- Cliente retoma com `Command(resume={"decision": "approved|rejected", "feedback": "..."})`
- Captura feedback em risk_flags na rejeicao

## Estado (TypedDicts)

### TravelPlannerCore (raiz)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| plan_id | str | Identificador unico do plano |
| destination | str | Cidade/regiao destino |
| dates | dict | start_date, end_date (ISO 8601) |
| budget | dict | total, currency, flexibility (0-1) |
| traveler_profile | dict | interests, pace, group_size |
| selected_flight_id | str or None | ID do voo selecionado |
| selected_hotel_id | str or None | ID do hotel selecionado |
| selected_activity_ids | list[str] | IDs das atividades selecionadas |
| current_cost | float | Custo total acumulado |
| revision_count | int | Re-otimizacoes por budget |
| approval_status | str | pending, in_review, approved, rejected |
| risk_flags | list[str] | Alertas de seguranca/politica |
| alternative_plans | dict | Planos alternativos / competitor data |
| destination_analysis | dict or None | Clima, eventos, advisories |
| hotel_options | list[dict] | Top 5 hoteis encontrados |
| activity_options | list[dict] | 15-20 atividades disponiveis |
| optimized_itinerary | dict or None | Agenda dia-a-dia final |

### TypedDicts Auxiliares

| TypedDict | Campos Chave | Usado Em |
|-----------|-------------|----------|
| WeatherForecast | date, condition, temp_max, temp_min, rain_chance, wind_speed | analyze_destination |
| WeatherSummary | avg_temp_max, avg_rain_chance, dominant_condition, severe_weather_days | analyze_destination |
| SeasonalEvent | name, category, description, month_start, month_end | analyze_destination |
| HotelOption | id, name, stars, price_per_night, amenities, reviews_score, score | search_hotels |
| Activity | id, name, category, duration_minutes, price, indoor, score | search_activities |
| OptimizedItinerary | days, unscheduled_activity_ids, optimization_method, validation_iterations | optimize_itinerary |
| ItineraryDay | date, day_number, theme, slots, weather_condition, notes | optimize_itinerary |
| ItinerarySlot | activity_id, activity_name, start_time, end_time, travel_time | optimize_itinerary |
| FlightOption | id, airline, departure_time, price, stops, carbon_footprint_kg | search_flights (stub) |
| ValidationResult | is_valid, issues, severity, suggested_fixes | validators |
| TravelVibe | destination_suggestions, vibe_tags, budget_tier_guess, activity_bias | image_analyzer |

## MCP Servers

### Weather (`mcp_servers/weather/`)

Fornece previsao climatica e alertas para o destino.

| Funcao Client | Retorno | Descricao |
|---------------|---------|-----------|
| `get_weather_forecast(dest, start, end)` | `list[WeatherForecast]` | Previsao diaria para o periodo |
| `get_weather_alerts(dest)` | `list[dict]` | Alertas ativos (tempestades, etc.) |

**Provider**: OpenWeather API (se key disponivel) ou mock deterministico.

### Hotels (`mcp_servers/hotels/`)

Busca e ranqueia opcoes de hospedagem.

| Funcao Client | Retorno | Descricao |
|---------------|---------|-----------|
| `search_hotels(dest, check_in, check_out, ...)` | `list[dict]` | Hoteis ranqueados por score |

**Provider**: Enuygun API (se OAuth configurado) ou mock deterministico.
**Scoring**: Preco, reviews, amenities match, centralidade.
**Retry**: Logica de retry com backoff exponencial.

### Activities (`mcp_servers/activities/`)

Descobre atividades e eventos no destino.

| Funcao Client | Retorno | Descricao |
|---------------|---------|-----------|
| `discover_activities(dest, interests, start, end, budget_per_day)` | `list[dict]` | Atividades filtradas e ranqueadas |

**Provider**: Mock com 50+ atividades pre-definidas por destino.
**Filtragem**: Interesses do viajante, horarios de funcionamento, budget.

### Context (`mcp_servers/context/`)

Armazena e recupera preferencias do usuario.

| Funcao Client | Retorno | Descricao |
|---------------|---------|-----------|
| `get_user_preferences(user_id)` | `dict` | Todas as preferencias |
| `get_travel_style(user_id)` | `dict` | Estilo de viagem |
| `get_accommodation_preferences(user_id)` | `dict` | Preferencias de hospedagem |

**Storage**: In-memory key-value store (InMemoryStore).

## Validators

### ItineraryValidator (`validators/itinerary_validator.py`)

Classe estatica com validacoes deterministicas:

| Metodo | Verifica |
|--------|----------|
| `validate_geographic_coherence(activities, hotel, max_travel=90min)` | Distancia Haversine hotel-atividades. Alerta se tempo de viagem > threshold. |
| `validate_timing_conflicts(activities, date)` | Max 6 atividades/dia, min 30 min cada, horarios de funcionamento. |
| `validate_budget_constraints(state)` | current_cost <= budget.total (error), margem < 10% (warning). |

### WeatherValidator (`validators/weather_validator.py`)

| Metodo | Verifica |
|--------|----------|
| `validate_outdoor_activities(activities, forecast)` | Atividades outdoor com chuva >= 60%, vento >= 50 km/h, temp extremas. |
| `validate_weather_suitability(forecast)` | Condicoes severas (tempestade, furacao), ventos perigosos. |

Ambos retornam `ValidationResult = {is_valid, issues, severity, suggested_fixes}`.
