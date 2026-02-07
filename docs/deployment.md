# Deployment

## Docker

### Portas

| Porta | Servico | Descricao |
|-------|---------|-----------|
| 8000 | FastAPI API | REST API + WebSocket + metricas + health |
| 3000 | Frontend | React SPA (servido com `serve`) |
| 5173 | Vite Dev | Dev server do frontend (desenvolvimento) |
| 6379 | Redis | Cache e armazenamento de estado |
| 9090 | Prometheus | Interface de monitoramento |

### Build e Execucao

```bash
# Build da imagem
docker build -t travel-orchestrator .

# Executar standalone
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  travel-orchestrator
```

### Docker Compose (stack completa)

```bash
# Criar arquivo .env com suas chaves
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Subir todos os servicos
docker compose up --build

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f api
```

#### Servicos

| Servico | Imagem | Funcao |
|---------|--------|--------|
| `api` | Build local (Python) | FastAPI REST API + WebSocket + metrics |
| `frontend` | Build local (Node) | React SPA servido com `serve` |
| `redis` | redis:7-alpine | Cache e state storage |
| `prometheus` | prom/prometheus:latest | Coleta e armazena metricas |

#### Rede Docker

Os servicos se comunicam pela rede interna do Docker Compose:
- `api` acessa Redis via `redis://redis:6379/0`
- `frontend` depende de `api` e proxia via Vite ou `serve`
- `prometheus` scrapa metricas de `api:8000/metrics`

### Dockerfile

O Dockerfile usa Python 3.11-slim e Poetry:

1. Instala dependencias de sistema (`build-essential`, `curl`)
2. Instala Poetry via script oficial
3. Copia `pyproject.toml` primeiro (cache de layer)
4. Instala dependencias sem dev (`--without dev`)
5. Copia codigo fonte
6. Configura healthcheck em `/health`
7. Usa `scripts/entrypoint.sh` como ENTRYPOINT

#### Entrypoint

O script `scripts/entrypoint.sh` inicia um unico processo:
1. **Uvicorn** (foreground via `exec`): FastAPI API server na porta 8000

### Healthcheck

```bash
# Dentro do container
curl http://localhost:8000/health
# {"status": "healthy"}

# De fora (com port mapping)
curl http://localhost:8000/health
```

O Docker HEALTHCHECK executa a cada 30s com timeout de 5s.

## Prometheus

### Configuracao

O arquivo `prometheus.yml` define o scraping:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'travel-orchestrator'
    metrics_path: /metrics
    static_configs:
      - targets: ['api:8000']
```

### Metricas Disponiveis

| Metrica | Tipo | Labels | Descricao |
|---------|------|--------|-----------|
| `travel_plans_completed_total` | Counter | status | Planos completados (success/error) |
| `travel_plans_approved_total` | Counter | - | Planos aprovados |
| `travel_plans_rejected_total` | Counter | - | Planos rejeitados |
| `travel_planning_duration_seconds` | Histogram | - | Duracao do pipeline completo |
| `travel_plan_cost_dollars` | Histogram | - | Custo por plano |
| `travel_active_plannings` | Gauge | - | Planejamentos em andamento |
| `travel_node_execution_seconds` | Histogram | node_name | Tempo de execucao por node |

### Acessando

| Endpoint | URL | Descricao |
|----------|-----|-----------|
| Metricas raw | http://localhost:8000/metrics | Formato Prometheus text |
| Dashboard | http://localhost:8000/dashboard | Dashboard HTML com Chart.js |
| Prometheus UI | http://localhost:9090 | Interface nativa do Prometheus |

### Queries PromQL Uteis

```promql
# Taxa de sucesso dos planos
rate(travel_plans_completed_total{status="success"}[5m])

# Tempo medio de planejamento
rate(travel_planning_duration_seconds_sum[5m]) / rate(travel_planning_duration_seconds_count[5m])

# Node mais lento (p95)
histogram_quantile(0.95, rate(travel_node_execution_seconds_bucket[5m]))

# Planejamentos ativos agora
travel_active_plannings

# Taxa de aprovacao
travel_plans_approved_total / (travel_plans_approved_total + travel_plans_rejected_total)
```

## Execucao Local (sem Docker)

### Pre-requisitos

- Python 3.11+
- Poetry
- Redis (opcional, para state persistence)

### Instalacao

```bash
# Instalar dependencias
poetry install

# Ativar virtualenv
poetry shell

# Ou usar PYTHONPATH
export PYTHONPATH=src
```

### Executando

```bash
# API server (porta 8000)
uvicorn travel_orchestrator.api.main:app --port 8000

# Ou via modulo legado
python -m travel_orchestrator.frontend
```

### Testes

```bash
# Todos os testes
PYTHONPATH=src python -m pytest tests/ -q

# Apenas unitarios
PYTHONPATH=src python -m pytest tests/unit/ -v

# Arquivo especifico
PYTHONPATH=src python -m pytest tests/unit/test_metrics.py -v

# Com cobertura
PYTHONPATH=src python -m pytest tests/ --cov=travel_orchestrator
```
