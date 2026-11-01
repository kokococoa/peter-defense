#!/usr/bin/env bash
# Source this script to activate ROS in the current shell.
_ros_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo 'ROS Humble is unavailable; run this inside the container.' >&2
  return 1 2>/dev/null || exit 1
fi
# ROS setup scripts may reference unset variables.
_ros_nounset=0
[[ $- == *u* ]] && _ros_nounset=1
set +u
source /opt/ros/humble/setup.bash
if [[ -f "$_ros_dir/ros2_ws/install/setup.bash" ]]; then source "$_ros_dir/ros2_ws/install/setup.bash"; fi
if (( _ros_nounset )); then set -u; fi
unset _ros_dir _ros_nounset
