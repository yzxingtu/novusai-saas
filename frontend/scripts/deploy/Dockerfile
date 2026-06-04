FROM node:22-slim AS builder

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV NODE_OPTIONS=--max-old-space-size=8192
ENV TZ=Asia/Shanghai

ARG VITE_GLOB_API_URL=https://api.novusai.example.com
ARG VITE_PLATFORM_DOMAINS=
ARG VITE_APP_TITLE="NovusAI SaaS"
ARG VITE_APP_NAMESPACE=novusai-web-saas
ARG VITE_APP_STORE_SECURE_KEY=change-me-before-production

ENV VITE_GLOB_API_URL="${VITE_GLOB_API_URL}" \
    VITE_PLATFORM_DOMAINS="${VITE_PLATFORM_DOMAINS}" \
    VITE_APP_TITLE="${VITE_APP_TITLE}" \
    VITE_APP_NAMESPACE="${VITE_APP_NAMESPACE}" \
    VITE_APP_STORE_SECURE_KEY="${VITE_APP_STORE_SECURE_KEY}"

RUN set -eu; \
    test -n "$VITE_APP_TITLE" || { echo "VITE_APP_TITLE must be set for production images" >&2; exit 1; }; \
    case "$VITE_APP_STORE_SECURE_KEY" in \
      ""|*example.invalid*|*example.com*|*localhost*|*127.0.0.1*|*0.0.0.0*|*.local*|*replace-me*|*please-replace*|*change-me*|your-secret-key-change-in-production) \
        echo "VITE_APP_STORE_SECURE_KEY must be replaced for a production image" >&2; \
        exit 1; \
        ;; \
    esac; \
    case "$VITE_GLOB_API_URL" in \
      http://localhost*|http://127.0.0.1*|http://backend-api*) \
        echo "Using local/dev API URL: $VITE_GLOB_API_URL" ;; \
      https://*) \
        ;; \
      *) \
        echo "VITE_GLOB_API_URL must start with https:// for production images (or be a local dev URL)" >&2; \
        exit 1; \
        ;; \
    esac; \
    case "$VITE_GLOB_API_URL" in \
      http://localhost*|http://127.0.0.1*|http://backend-api*) \
        ;; \
      *example.invalid*|*example.com*|*localhost*|*127.0.0.1*|*0.0.0.0*) \
        echo "VITE_GLOB_API_URL must be a real HTTPS production URL" >&2; \
        exit 1; \
        ;; \
    esac; \
    case "$VITE_PLATFORM_DOMAINS" in \
      ""|*example.invalid*|*example.com*|*localhost*|*127.0.0.1*|*0.0.0.0*) \
        echo "VITE_PLATFORM_DOMAINS must be replaced with real production domains" >&2; \
        exit 1; \
        ;; \
    esac

RUN corepack enable

WORKDIR /app

COPY frontend /app
COPY backend/app /backend/app
COPY backend/plugins /backend/plugins

RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
RUN pnpm --filter @vben/web-antd build

RUN test -f /app/apps/web-antd/dist/index.html

FROM nginx:stable-alpine AS production

RUN rm -rf /etc/nginx/conf.d/default.conf \
    && mkdir -p /var/cache/nginx /var/run /tmp/nginx \
    && chown -R nginx:nginx /var/cache/nginx /var/run /tmp/nginx /usr/share/nginx/html /etc/nginx

COPY --from=builder --chown=nginx:nginx /app/apps/web-antd/dist /usr/share/nginx/html

COPY --from=builder --chown=nginx:nginx /app/scripts/deploy/nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

USER nginx

CMD ["nginx", "-g", "daemon off;"]
