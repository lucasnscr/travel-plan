# Configuracao

## Variaveis de Ambiente

Todas as variaveis sao gerenciadas via `pydantic-settings` e podem ser definidas
em um arquivo `.env` na raiz do projeto ou como variaveis de ambiente do sistema.

### API Keys

| Variavel | Obrigatoria | Default | Descricao |
|----------|-------------|---------|-----------|
| `ANTHROPIC_API_KEY` | Sim | - | Chave da API Anthropic (Claude) |
| `OPENAI_API_KEY` | Nao | None | Chave OpenAI para transcricao Whisper |
| `LANGSMITH_API_KEY` | Nao | None | Chave para tracing LangSmith |

### LLM

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `MODEL_NAME` | `claude-sonnet-4-20250514` | Modelo Claude a usar |
| `TEMPERATURE` | `0.3` | Temperatura de sampling (0-1) |
| `MAX_TOKENS` | `4096` | Max tokens por resposta (100-8192) |

### Sistema

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `LOG_LEVEL` | `INFO` | Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `ENVIRONMENT` | `development` | development = console colorido, production = JSON |

### Budget

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `MAX_BUDGET_USD` | `50000.0` | Budget maximo absoluto aceito pelo sistema |
| `APPROVAL_THRESHOLD_USD` | `10000.0` | Acima deste valor, requer aprovacao explicita |

### Performance

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `MAX_RETRIES` | `3` | Retries para chamadas de tool/API |
| `TIMEOUT_SECONDS` | `30` | Timeout padrao para operacoes |

### Enuygun MCP (Hoteis)

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `ENUYGUN_MCP_URL` | `https://mcp.enuygun.com/mcp` | Endpoint do MCP Enuygun |
| `ENUYGUN_OAUTH_CLIENT_ID` | None | Client ID para OAuth |
| `ENUYGUN_OAUTH_CLIENT_SECRET` | None | Client Secret para OAuth |
| `ENUYGUN_OAUTH_TOKEN_URL` | None | URL para obter token OAuth |
| `ENUYGUN_OAUTH_SCOPE` | None | Scope do OAuth |

### Storage

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `REDIS_URL` | `redis://localhost:6379/0` | Conexao Redis |
| `POSTGRES_URL` | None | Conexao PostgreSQL (opcional) |

## Exemplo .env

```bash
# Obrigatorio
ANTHROPIC_API_KEY=sk-ant-...

# Opcional - multimodal
OPENAI_API_KEY=sk-...

# Opcional - tracing
LANGSMITH_API_KEY=lsv2_...

# LLM
MODEL_NAME=claude-sonnet-4-20250514
TEMPERATURE=0.3

# Sistema
LOG_LEVEL=INFO
ENVIRONMENT=development

# Storage
REDIS_URL=redis://localhost:6379/0
```

## Constantes de Negocio

Definidas em `src/travel_orchestrator/config/constants.py`. Sao regras fixas
que nao dependem de ambiente.

### Restricoes de Itinerario

| Constante | Valor | Descricao |
|-----------|-------|-----------|
| `MAX_DAILY_TRAVEL_TIME_MINUTES` | 90 | Tempo maximo de deslocamento por dia |
| `MAX_ACTIVITIES_PER_DAY` | 6 | Maximo de atividades em um unico dia |
| `MIN_ACTIVITY_DURATION_MINUTES` | 30 | Duracao minima de cada atividade |

### Otimizacao de Itinerario

| Constante | Valor | Descricao |
|-----------|-------|-----------|
| `MAX_OPTIMIZATION_ITERATIONS` | 3 | Iteracoes LLM + validator |
| `PACE_ACTIVITIES_PER_DAY` | fast=5, moderate=3, slow=2 | Atividades por ritmo |
| `DEFAULT_DAY_START_HOUR` | "09:00" | Inicio padrao do dia |
| `DEFAULT_DAY_END_HOUR` | "20:00" | Fim padrao do dia |
| `TRAVEL_BUFFER_MINUTES` | 15 | Buffer entre atividades |
| `RAIN_THRESHOLD_FOR_INDOOR` | 60.0 | Chance de chuva (%) que favorece indoor |

### Moedas

| Constante | Valor | Descricao |
|-----------|-------|-----------|
| `SUPPORTED_CURRENCIES` | USD, BRL, EUR | Moedas suportadas |

## Alocacao de Budget

O sistema distribui o budget total entre os servicos:

| Servico | Alocacao | Definido Em |
|---------|----------|-------------|
| Hoteis | 35% do total | `search_hotels.py` |
| Atividades | 20% do total | `search_activities.py` |
| Voos | Restante | (stub) |

### Re-otimizacao de Custos

Se `current_cost` exceder o teto apos `calculate_budget`, o grafo
re-executa o ciclo de busca ate `MAX_REVISION_COUNT` (3) vezes.

```
teto = max(budget.total * (1 + flexibility), budget.total * 1.10)
```

A flexibility padrao e 0.1 (10%), permitindo uma margem de ate 10% acima do budget.
