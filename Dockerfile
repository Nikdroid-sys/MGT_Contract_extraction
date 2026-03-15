# Use a slim 2026-standard image
FROM python:3.12-slim-bookworm

# 1. Set environment variables for optimization
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# 2. Install uv using the official binary (Fastest)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 3. Cache dependencies separately from source code
# This layer only rebuilds if pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 4. Copy application files
COPY app ./app
COPY config ./config
COPY main.py ./

# 5. Final sync to install the actual project logic
RUN uv sync --frozen --no-dev

# 6. Security: Run as a non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# 7. Render assigns $PORT; bind to 0.0.0.0 so it's reachable
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT}"]