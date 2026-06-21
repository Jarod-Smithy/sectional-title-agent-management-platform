# Local-dev / container image for the Dashboard API.
# Production runs the same app on Lambda via app.main.handler (Mangum); this
# image is for `docker compose up` and ECS/Fargate fallback.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

COPY app ./app

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown -R appuser /app/data
USER appuser

ENV STAK_DATA_DIR=/app/data \
    STAK_SERVE_STATIC=false

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
