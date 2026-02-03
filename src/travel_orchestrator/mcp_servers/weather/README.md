# Weather MCP Server

MCP tool server that provides weather forecast and alert data for travel planning.

## Tools

| Tool | Description |
|---|---|
| `get_weather_forecast` | Daily forecast for a destination + date range |
| `get_weather_alerts` | Severe weather alerts for a destination |

## Data Sources

### Mock Provider (default)

When no OpenWeatherMap API key is configured, the server returns **deterministic mock data** based on:

- Destination latitude (tropical / temperate / polar / arid)
- Month (summer vs winter per hemisphere)
- Seeded RNG — same inputs always produce the same outputs

This is sufficient for development and testing.

### OpenWeatherMap (live)

To enable live data:

1. Create a free account at [openweathermap.org](https://openweathermap.org/api)
2. Subscribe to the **One Call API 3.0** (free tier: 1,000 calls/day)
3. Add to your `.env`:

```bash
OPENWEATHERMAP_API_KEY=your-key-here
```

4. Add the field to `Settings` in `config/settings.py`:

```python
openweathermap_api_key: str | None = Field(None, description="OpenWeatherMap API key")
```

The server automatically falls back to mock data if the live API call fails.

## Running Standalone

```bash
# stdio transport (for MCP client integration)
python -m travel_orchestrator.mcp_servers.weather.server
```

## Usage from MCP Client

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["-m", "travel_orchestrator.mcp_servers.weather.server"],
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

## Example Tool Calls

### get_weather_forecast

```json
{
  "name": "get_weather_forecast",
  "arguments": {
    "destination": "Tokyo",
    "start_date": "2025-04-01",
    "end_date": "2025-04-03"
  }
}
```

Response:

```json
[
  {
    "date": "2025-04-01",
    "condition": "partly_cloudy",
    "temp_max": 18.2,
    "temp_min": 9.5,
    "rain_chance": 15.0,
    "rain_start": null,
    "wind_speed": 12.3
  }
]
```

### get_weather_alerts

```json
{
  "name": "get_weather_alerts",
  "arguments": {
    "destination": "Tokyo"
  }
}
```

Response (when no alerts):

```json
[]
```
