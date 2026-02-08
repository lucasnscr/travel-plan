# Travel Orchestrator - Documentacao

## Visao Geral

Sistema de planejamento de viagens com agentes AI que demonstra padroes de producao:
- **LangGraph**: Orquestracao de workflow complexo com 12 nodes e roteamento condicional
- **MCP**: Integracao padronizada de tools e context (weather, hotels, activities, preferences)
- **A2A**: Delegacao entre agentes especializados (multimodal, validators, output)
- **UCP**: Jornada de usuario padronizada com HITL (Human-in-the-Loop)

## Arquitetura

```
                         +-----------------+
                         |   FastAPI SPA   |  :7860
                         | Tailwind CSS UI |
                         | /metrics /health|
                         +--------+--------+
                                  |
                   +--------------+--------------+
                   |                             |
          +--------v--------+          +---------v---------+
          |   Multimodal    |          |    REST API        |
          | - Audio (Whisper)|         | - POST /api/plan   |
          | - Image (Vision)|          | - POST /api/approve|
          | - PDF (Claude)  |          | - GET /dashboard   |
          +---------+-------+          +--------------------+
                    |
          +---------v----------------------------------+
          |        LangGraph State Machine             |
          |                                            |
          |  gather       analyze       search         |
          |  require- --> destina- -->  flights -->     |
          |  ments        tion          (stub)         |
          |                                 |          |
          |  search    search     optimize  |          |
          |  hotels <-- activi- <-- itiner- <          |
          |    |       ties        ary                 |
          |    v                                       |
          |  calculate   risk &     present            |
          |  budget  --> policy --> for     -->         |
          |    ^         check     approval            |
          |    |                      |                |
          |    +--- over budget ------+  rejected      |
          |         (max 3x)         |                 |
          |                    +-----v------+          |
          |                    | book / gen |          |
          |                    | (stubs)    |          |
          +--------------------+------------+----------+
                    |
     +--------------+--------------+
     |              |              |
+----v----+  +------v------+  +---v--------+
|   MCP   |  |   MCP       |  |   MCP      |
| Weather |  |   Hotels    |  | Activities |
| Server  |  |   Server    |  |   Server   |
+---------+  | (Enuygun)   |  +------------+
             +-------------+
     +--------------+--------------+
     |              |              |
+----v----+  +------v------+  +---v--------+
|Itinerary|  |  Weather    |  | Prometheus |
|Validator|  |  Validator  |  |  Metrics   |
+---------+  +-------------+  +------------+
```

## Indice da Documentacao

| Documento | Descricao |
|-----------|-----------|
| [Arquitetura](architecture.md) | Grafo de estados, nodes, edges, fluxo de dados |
| [Configuracao](configuration.md) | Variaveis de ambiente, constantes de negocio |
| [Deployment](deployment.md) | Docker, docker-compose, Prometheus |
| [Referencia da API](api-reference.md) | Funcoes publicas de cada modulo |

## Demo Mode

O sistema inclui um modo de demonstracao otimizado para apresentacoes ao vivo, com dados pre-carregados de uma viagem de 5 dias a Tokyo.

### Ativacao

Pressione a tecla **D** em qualquer pagina para ativar/desativar o Demo Mode. Um painel de controle aparecera no canto inferior direito.

### Controles

| Tecla | Acao |
|-------|------|
| `D` | Ativar/desativar Demo Mode |
| `Space` | Play/Stop auto-play |
| `H` | Ativar/desativar tooltips explicativos |
| `1`-`5` | Navegar para o dia correspondente no mapa |
| `O` | Abrir aba do Orchestrator |
| `F` | Fullscreen no mapa |
| `R` | Resetar demonstracao |
| `Escape` | Sair do Demo Mode |

### Velocidades

- **Fast**: Execucao quase instantanea (0.05x) — ideal para debug
- **Normal**: Velocidade padrao (1x) — ~30 segundos total
- **Slow**: Pausas dramaticas (2.5x) — ideal para apresentacoes ao vivo

### Auto-Play

O botao "Play Demo" executa uma sequencia automatizada que demonstra todo o fluxo:

1. Reset do ambiente e exibicao do formulario de planejamento
2. Disparo do pipeline LangGraph com dados pre-carregados (Tokyo 5 dias)
3. Visualizacao do orchestrator com simulacao dos 12 nodes
4. Destaque dos MCP Servers buscando dados de clima, hoteis e atividades
5. Pausa dramatica no gate Human-in-the-Loop
6. Exibicao dos resultados: hoteis ranqueados, atividades curadas, itinerario
7. Fly-through no mapa interativo pelos 5 dias da viagem
8. Timeline drag-and-drop com persistencia via REST API

### Highlight Mode

Pressione **H** durante o Demo Mode para exibir tooltips explicativos sobre cada componente da interface, destacando as tecnologias utilizadas (LangGraph, MCP, Human-in-the-Loop, WebSocket streaming, etc.).

## Quick Start

```bash
# 1. Clone e instale
git clone <repo-url>
cd travel-orchestrator
poetry install

# 2. Configure variaveis de ambiente
cp .env.example .env
# Edite .env com suas chaves API

# 3. Execute a interface
python -m travel_orchestrator.frontend

# 4. Execute com Docker
docker compose up --build
```

## Estrutura do Projeto

```
travel-orchestrator/
|-- src/travel_orchestrator/
|   |-- agents/              # Agentes especializados (reservado)
|   |-- config/              # Settings e constantes de negocio
|   |-- frontend/            # FastAPI SPA + dashboard HTML
|   |-- graph/               # LangGraph: planner_graph, edges, nodes/
|   |-- mcp_servers/         # Weather, Hotels, Activities, Context
|   |-- models/              # Modelos de dominio (reservado)
|   |-- multimodal/          # Audio, Image, PDF processors
|   |-- observability/       # Prometheus metrics + FastAPI server
|   |-- output/              # Map (Folium) + PDF (ReportLab) generators
|   |-- state/               # TypedDicts (TravelPlannerCore, etc.)
|   |-- utils/               # Structured logging, decorators
|   +-- validators/          # Itinerary + Weather validation
|-- tests/
|   |-- unit/                # ~746 testes unitarios
|   +-- integration/         # Testes de integracao
|-- docs/                    # Esta documentacao
|-- Dockerfile               # Container de producao
|-- docker-compose.yml       # Stack completa (app + Redis + Prometheus)
|-- prometheus.yml           # Configuracao de scraping
+-- pyproject.toml           # Dependencias e configuracao
```

## Stack Tecnologica

| Componente | Tecnologia | Versao |
|------------|-----------|--------|
| Orquestracao | LangGraph | >= 0.2.28 |
| LLM | Claude (langchain-anthropic) | >= 0.3.0 |
| API Client | Anthropic SDK | >= 0.39.0 |
| MCP | mcp | >= 1.1.0 |
| Config | Pydantic Settings | >= 2.0 |
| Logging | structlog | >= 24.0 |
| Frontend | FastAPI + Tailwind CSS | >= 0.115 |
| Mapas | Folium | >= 0.15 |
| PDF | ReportLab | >= 4.0 |
| Transcricao | OpenAI Whisper (via httpx) | >= 0.27 |
| Metricas | prometheus-client | >= 0.20 |
| Server | Uvicorn | >= 0.32 |
| Testes | pytest + pytest-asyncio | >= 8.0 |
