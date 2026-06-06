FROM node:22-slim AS builder

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV NODE_OPTIONS=--max-old-space-size=8192
ENV TZ=Asia/Shanghai

# Build-time args — baked into the JS bundle (import.meta.env.VITE_*)
ARG VITE_GLOB_API_URL=https://api.novusai.example.com
ARG VITE_PLATFORM_DOMAINS=localhost
ARG VITE_APP_TITLE="NovusAI SaaS"
ARG VITE_APP_NAMESPACE=novusai-web-saas
ARG VITE_APP_STORE_SECURE_KEY=change-me-before-production

ENV VITE_GLOB_API_URL="${VITE_GLOB_API_URL}" \
    VITE_PLATFORM_DOMAINS="${VITE_PLATFORM_DOMAINS}" \
    VITE_APP_TITLE="${VITE_APP_TITLE}" \
    VITE_APP_NAMESPACE="${VITE_APP_NAMESPACE}" \
    VITE_APP_STORE_SECURE_KEY="${VITE_APP_STORE_SECURE_KEY}"

RUN corepack enable

WORKDIR /app

COPY frontend /app
COPY VERSION /
COPY backend/app /backend/app
COPY backend/plugins /backend/plugins

# Write VITE_GLOB_* env vars into .env.production so the runtime _app.config.js picks them up
RUN printf 'VITE_GLOB_API_URL=%s\n' "$VITE_GLOB_API_URL" > /app/apps/web-antd/.env.production

RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
RUN pnpm --filter @vben/web-antd... build

RUN test -f /app/apps/web-antd/dist/index.html

FROM nginx:stable-alpine AS production

RUN rm -rf /etc/nginx/conf.d/default.conf \
    && mkdir -p /var/cache/nginx /var/run /tmp/nginx \
    && chown -R nginx:nginx /var/cache/nginx /var/run /tmp/nginx /usr/share/nginx/html /etc/nginx

COPY --from=builder --chown=nginx:nginx /app/apps/web-antd/dist /usr/share/nginx/html

COPY --from=builder --chown=nginx:nginx /app/scripts/deploy/nginx.conf /etc/nginx/nginx.conf

# Runtime config — override VITE_GLOB_* vars at container startup via docker-compose.yml
ENV VITE_GLOB_API_URL=https://api.novusai.example.com

COPY --chmod=755 frontend/scripts/deploy/entrypoint.sh /entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

USER nginx

ENTRYPOINT ["/entrypoint.sh"]
