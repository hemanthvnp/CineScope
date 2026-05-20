#!/bin/sh
set -e
export PORT="${PORT:-80}"
export BACKEND_URL="${BACKEND_URL:-http://backend:5000}"
export BACKEND_HOST="${BACKEND_HOST:-backend:5000}"
envsubst '${PORT} ${BACKEND_URL} ${BACKEND_HOST}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
