#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ $# == 0 ]] || { echo 'Usage: ros_clean.sh' >&2; exit 2; }
rm -rf -- "$DIR/ros2_ws/build" "$DIR/ros2_ws/install" "$DIR/ros2_ws/log"
