#!/usr/bin/env bash
set -eo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "${PETER_SIDE:-remote}" in
  remote) package=peter_defense_remote; executable=camera_publisher;;
  main) package=peter_defense_main; executable=image_subscriber;;
  *) echo 'PETER_SIDE must be remote or main.' >&2; exit 2;;
esac
source "$DIR/ros_activate.sh"
cd "$DIR/ros2_ws"
exec ros2 run "$package" "$executable" "$@"
