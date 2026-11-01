#!/usr/bin/env bash
set -eo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/ros_activate.sh"
cd "$DIR/ros2_ws"
exec colcon build --symlink-install "$@"
