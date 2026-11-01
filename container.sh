#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
usage() { echo "Usage: bash container.sh [remote|main] {attach|start|stop} [container name]" >&2; exit 2; }
# Load only validated configuration values; never execute .env as shell code.
side=""
if [[ -f "$ROOT/.env" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in PETER_SIDE) side="$value";; ROS_DOMAIN_ID) [[ "$value" =~ ^[0-9]+$ ]] || usage; export ROS_DOMAIN_ID="$value";; esac
  done < "$ROOT/.env"
fi
if [[ "${1:-}" == remote || "${1:-}" == main ]]; then side="$1"; shift; fi
[[ "$side" == remote || "$side" == main ]] || { echo 'Run setup.sh or specify remote/main.' >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
action="$1"
export PETER_SIDE="$side"
export PETER_CONTAINER_NAME="${2:-ros-peter-$side}"
[[ "$PETER_CONTAINER_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || usage
compose=(docker compose --project-directory "$ROOT" -f "$ROOT/compose.yaml" --profile "$side")
case "$action" in
  start) "${compose[@]}" up -d --build "$side";;
  stop) "${compose[@]}" down;;
  attach) exec docker exec -it "$PETER_CONTAINER_NAME" bash;;
  *) usage;;
esac
