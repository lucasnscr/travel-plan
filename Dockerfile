FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files first (layer caching)
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev, no virtualenv)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --without dev

# Copy application source
COPY src/ ./src/

# Copy entrypoint
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port: 8000 = FastAPI API
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
