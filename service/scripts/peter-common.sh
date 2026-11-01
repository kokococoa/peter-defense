#!/usr/bin/env bash
set -euo pipefail
side="${1:?Expected main or remote}"
action="${2:-start}"
case "$side" in main|remote) ;; *) echo 'Invalid machine role.' >&2; exit 2;; esac
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
export PETER_SIDE="$side"
export PETER_CONTAINER_NAME="ros-peter-$side"
compose=(docker compose --project-name peter-defense --project-directory "$ROOT"
  --env-file "$ROOT/.env" -f "$ROOT/compose.yaml" -f "$ROOT/service/compose.yaml"
  --profile "$side")
case "$action" in
  start)
    if [[ "$side" == remote ]]; then
      for ((attempt=0; attempt<60; attempt++)); do
        [[ -c /dev/video0 ]] && break
        sleep 1
      done
      [[ -c /dev/video0 ]] || { echo '/dev/video0 did not appear within 60 seconds.' >&2; exit 1; }
    fi
    exec "${compose[@]}" up -d --no-build "$side"
    ;;
  stop) exec "${compose[@]}" stop --timeout 15 "$side";;
  *) echo "Usage: peter-$side.sh [start|stop]" >&2; exit 2;;
esac
