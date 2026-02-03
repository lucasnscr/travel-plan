"""Constantes determinísticas usadas por validators e graph nodes.

Estes valores não dependem de ambiente — são regras de negócio fixas
do planejador de viagens.
"""

# Itinerary constraints
MAX_DAILY_TRAVEL_TIME_MINUTES: int = 90
MAX_ACTIVITIES_PER_DAY: int = 6
MIN_ACTIVITY_DURATION_MINUTES: int = 30

# Itinerary optimization
MAX_OPTIMIZATION_ITERATIONS: int = 3
PACE_ACTIVITIES_PER_DAY: dict[str, int] = {"fast": 5, "moderate": 3, "slow": 2}
DEFAULT_DAY_START_HOUR: str = "09:00"
DEFAULT_DAY_END_HOUR: str = "20:00"
TRAVEL_BUFFER_MINUTES: int = 15
RAIN_THRESHOLD_FOR_INDOOR: float = 60.0

# Currency
SUPPORTED_CURRENCIES: list[str] = ["USD", "BRL", "EUR"]
