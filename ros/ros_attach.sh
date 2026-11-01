#!/usr/bin/env bash
# Interactive Bash startup for container.sh attach.
if [[ -f ~/.bashrc ]]; then source ~/.bashrc; fi
source /ros/ros_activate.sh
# Keep the debugging shell open when an interactive command fails.
set +e +u
