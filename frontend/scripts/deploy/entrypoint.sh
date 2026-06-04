#!/bin/sh
set -e

# ── Generate _app.config.js from VITE_GLOB_* runtime env vars ─────────────
# This allows the frontend API URL (and other GLOB config) to be set via
# docker-compose.yml ENVIRONMENT at container startup, instead of being
# baked into the image at build time.

CONFIG="{"
FIRST=true

for VAR_PAIR in $(env | grep '^VITE_GLOB_' | sort); do
  KEY=$(printf '%s' "$VAR_PAIR" | cut -d'=' -f1)
  VALUE=$(printf '%s' "$VAR_PAIR" | cut -d'=' -f2- | sed 's/\\/\\\\/g; s/"/\\"/g')
  if [ "$FIRST" = true ]; then
    FIRST=false
  else
    CONFIG="$CONFIG,"
  fi
  CONFIG="$CONFIG\"$KEY\":\"$VALUE\""
done
CONFIG="$CONFIG}"

cat > /usr/share/nginx/html/_app.config.js << JS_EOF
window._VBEN_ADMIN_PRO_APP_CONF_=$CONFIG;Object.freeze(window._VBEN_ADMIN_PRO_APP_CONF_);Object.defineProperty(window,"_VBEN_ADMIN_PRO_APP_CONF_",{configurable:false,writable:false});
JS_EOF

printf '[entrypoint] _app.config.js generated with keys: '
env | grep '^VITE_GLOB_' | cut -d'=' -f1 | sort | tr '\n' ' '
printf '\n'

exec nginx -g 'daemon off;'
