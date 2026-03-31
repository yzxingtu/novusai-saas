FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# Production images must not install optional dev extras (smaller attack surface / 生产镜像不装 dev 可选依赖)
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir .

COPY . .

FROM base AS api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

FROM base AS worker

CMD ["celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=info", "--concurrency=4"]

FROM base AS beat

CMD ["celery", "-A", "app.celery_app:celery_app", "beat", "--loglevel=info"]
