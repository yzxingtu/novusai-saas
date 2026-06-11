FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do \
        [ -e "$f" ] || continue; \
        sed -i 's|http://deb.debian.org|https://deb.debian.org|g' "$f"; \
    done; \
    apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
    build-essential libcairo2-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml backend/README.md ./
COPY VERSION /
COPY VERSION ./
COPY backend/app ./app
# 中文: 元数据和源码都进入镜像后再执行一次正式安装，避免 fallback 掩盖构建问题。
# EN: Install once after metadata and source are present so fallback paths cannot mask build issues.
RUN pip install --prefix=/install --no-cache-dir .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do \
        [ -e "$f" ] || continue; \
        sed -i 's|http://deb.debian.org|https://deb.debian.org|g' "$f"; \
    done; \
    apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 novusai \
    && useradd --system --uid 10001 --gid novusai --home-dir /app --shell /usr/sbin/nologin novusai

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /VERSION /VERSION
COPY --from=builder --chown=novusai:novusai /app/VERSION /app/VERSION
COPY --chown=novusai:novusai backend/ .

RUN mkdir -p /app/logs /app/storage/uploads /app/storage/cache/images /app/var/celerybeat \
    && chown -R novusai:novusai /app

USER novusai

FROM runtime AS api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=5).read()" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

FROM runtime AS worker

CMD ["celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=info", "--pool=solo"]

FROM runtime AS beat

CMD ["celery", "-A", "app.celery_app:celery_app", "beat", "--loglevel=info", "--schedule=/app/var/celerybeat/celerybeat-schedule"]
