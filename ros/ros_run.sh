#!/usr/bin/env bash
set -eo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/ros_build.sh" --packages-select peter_defense_remote
source "$DIR/ros_activate.sh"
cd "$DIR/ros2_ws"
exec ros2 run peter_defense_remote camera_publisher "$@"
