#!/usr/bin/env bash
set -euo pipefail

HOST="${OPEN_WEBUI_MACMINI_HOST:-macmini.lan}"
PUBLIC_URL="${OPEN_WEBUI_PUBLIC_URL:-https://chat.ch5.me}"
TUNNEL_LABEL="${OPEN_WEBUI_TUNNEL_LABEL:-com.radbot.open-webui-cloudflared}"
CONTAINER_NAME="${OPEN_WEBUI_CONTAINER_NAME:-open-webui-devmux}"

echo "== Public =="
curl -fsS -o /dev/null -D - "$PUBLIC_URL" | sed -n '1,8p'

echo
echo "== Host launchd =="
ssh "$HOST" "launchctl print gui/$(id -u)/$TUNNEL_LABEL | sed -n '1,40p'"

echo
echo "== Host container =="
ssh "$HOST" "docker inspect $CONTAINER_NAME --format '{{.Name}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}'"

echo
echo "== Host port 24773 =="
ssh "$HOST" "curl -fsS -o /dev/null -D - http://127.0.0.1:24773/ | sed -n '1,8p'"
