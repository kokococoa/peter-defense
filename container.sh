#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
usage() { echo "Usage: bash container.sh {attach|start|stop} [container name]" >&2; exit 2; }
# Load only validated configuration values; never execute .env as shell code.
side=""
if [[ -f "$ROOT/.env" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in PETER_SIDE) side="$value";; ROS_DOMAIN_ID) [[ "$value" =~ ^[0-9]+$ ]] || usage; export ROS_DOMAIN_ID="$value";; esac
  done < "$ROOT/.env"
fi
[[ "$side" == remote || "$side" == main ]] || { echo 'Set PETER_SIDE=remote or main in .env by running setup.sh.' >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
action="$1"
export PETER_SIDE="$side"
export PETER_CONTAINER_NAME="${2:-ros-peter-$side}"
[[ "$PETER_CONTAINER_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || usage
compose=(docker compose --project-directory "$ROOT" -f "$ROOT/compose.yaml" --profile "$side")
case "$action" in
  start) "${compose[@]}" up -d --build "$side";;
  stop) "${compose[@]}" down;;
  attach)
    if running=$(docker inspect --type container --format '{{.State.Running}}' "$PETER_CONTAINER_NAME" 2>/dev/null); then
      if [[ "$running" != true ]]; then
        docker start "$PETER_CONTAINER_NAME"
      fi
    else
      # Distinguish Docker access failures from a container that does not exist.
      docker info >/dev/null
      if [[ $# == 2 ]]; then
        echo "Container '$PETER_CONTAINER_NAME' does not exist. Check the name or use 'bash container.sh attach' for this machine's default." >&2
        exit 1
      fi
      # Preserve automatic creation of the default container without rebuilding.
      "${compose[@]}" up -d --no-build "$side"
    fi
    gui_env=()
    if [[ "$side" == main && -n "${DISPLAY:-}" ]]; then
      command -v xauth >/dev/null || {
        echo 'Install xauth on the host to forward the current display into the container.' >&2
        exit 1
      }
      records=$(xauth nlist "$DISPLAY" 2>/dev/null || true)
      [[ -n "$records" ]] || {
        echo "No X11 authentication cookie found for DISPLAY=$DISPLAY. Reconnect with ssh -Y and attach from that SSH session." >&2
        exit 1
      }
      authfile="/tmp/peter-xauth-${DISPLAY//[^a-zA-Z0-9_.-]/_}"
      # Build the cookie on the host, then copy it without logging its contents.
      # FamilyWild makes the SSH cookie usable across host/container hostnames.
      (
        cookie=$(mktemp)
        trap 'rm -f -- "$cookie"' EXIT
        printf '%s\n' "$records" | sed 's/^..../ffff/' | xauth -f "$cookie" nmerge -
        docker exec -i "$PETER_CONTAINER_NAME" sh -c \
          'umask 077; rm -f -- "$1"; cat > "$1"' sh "$authfile" < "$cookie"
      )
      gui_env=(-e "DISPLAY=$DISPLAY" -e "XAUTHORITY=$authfile")
    fi
    exec docker exec -it "${gui_env[@]}" "$PETER_CONTAINER_NAME" bash --rcfile /ros/ros_attach.sh +e +u -i
    ;;
  *) usage;;
esac
