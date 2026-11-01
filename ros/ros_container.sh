#!/usr/bin/env bash
# Keep the container available for debugging after the ROS process exits.
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
bash "$DIR/ros_run.sh" "$@"
status=$?
printf 'ROS process exited with status %s. Container remains running; rerun with bash /ros/ros_run.sh.\n' "$status" >&2
exec sleep infinity
