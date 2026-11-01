#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEST=/opt/peter-defense
[[ $# -le 1 ]] || { echo 'Usage: bash service/install.sh [main|remote]' >&2; exit 2; }
side="${1:-}"
domain=0
if [[ -f "$ROOT/.env" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in
      PETER_SIDE) [[ -n "$side" ]] || side="$value";;
      ROS_DOMAIN_ID) domain="$value";;
    esac
  done < "$ROOT/.env"
fi
[[ "$side" == main || "$side" == remote ]] || {
  echo 'Run setup.sh first, or specify main/remote.' >&2; exit 2;
}
[[ "$domain" =~ ^[0-9]+$ ]] && ((10#$domain <= 232)) || {
  echo 'ROS_DOMAIN_ID must be an integer from 0 to 232.' >&2; exit 2;
}
if (( EUID != 0 )); then
  exec sudo bash "$ROOT/service/install.sh" "$side"
fi
export PATH="$PATH:/snap/bin"
command -v docker >/dev/null
command -v systemctl >/dev/null
docker compose version >/dev/null
daemon=''
for candidate in docker.service snap.docker.dockerd.service; do
  if [[ "$(systemctl show --property=LoadState --value "$candidate")" == loaded ]]; then
    daemon="$candidate"
    break
  fi
done
[[ -n "$daemon" ]] || { echo 'No Docker systemd service found.' >&2; exit 1; }
if [[ "$daemon" == snap.docker.dockerd.service ]]; then
  DEST=/var/snap/docker/common/peter-defense
  if [[ -e /opt/peter-defense && ! -L /opt/peter-defense && -e "$DEST" ]]; then
    echo 'Both /opt/peter-defense and the Snap deployment directory exist; refusing to overwrite either.' >&2
    exit 1
  fi
  if [[ -L /opt/peter-defense && "$(readlink -f /opt/peter-defense)" != "$DEST" ]]; then
    echo '/opt/peter-defense points to an unexpected directory.' >&2
    exit 1
  fi
fi
systemctl start "$daemon"
docker info >/dev/null
# Finish building before stopping any installed service.
bash "$ROOT/ros/docker/build.sh"
other=main
[[ "$side" == main ]] && other=remote
for role in "$other" "$side"; do
  if [[ "$(systemctl show --property=LoadState --value "peter-$role.service")" == loaded ]]; then
    systemctl stop "peter-$role.service"
    if [[ "$role" == "$other" ]]; then systemctl disable "peter-$role.service"; fi
  fi
done
if [[ "$daemon" == snap.docker.dockerd.service ]]; then
  if [[ -d /opt/peter-defense && ! -L /opt/peter-defense ]]; then
    mv /opt/peter-defense "$DEST"
    # The installer may itself be running from the deployment being migrated.
    if [[ "$ROOT" == /opt/peter-defense ]]; then ROOT="$DEST"; fi
  else
    install -d -m 0755 "$DEST"
  fi
  if [[ ! -L /opt/peter-defense ]]; then ln -s "$DEST" /opt/peter-defense; fi
fi
# A manually started container with this name must be replaced to adopt the
# installed paths and the system-service command. Other containers are untouched.
if docker container inspect "ros-peter-$side" >/dev/null 2>&1; then
  docker rm -f "ros-peter-$side"
fi
if [[ "$ROOT" != "$DEST" ]]; then
  install -d -m 0755 "$DEST"
  # Do not copy colcon outputs: rebuild against the installed workspace path.
  tar -C "$ROOT" --exclude=ros/ros2_ws/build --exclude=ros/ros2_ws/install \
    --exclude=ros/ros2_ws/log --exclude=__pycache__ --exclude='*.pyc' \
    -cf - compose.yaml container.sh ros service | tar -C "$DEST" -xf -
  rm -rf -- "$DEST/ros/ros2_ws/build" "$DEST/ros/ros2_ws/install" "$DEST/ros/ros2_ws/log"
fi
install -d -m 0755 /etc/systemd/system
for role in main remote; do
  sed "s/docker\.service/$daemon/g" "$DEST/service/unit/peter-$role.service" \
    > "/etc/systemd/system/peter-$role.service"
  chmod 0644 "/etc/systemd/system/peter-$role.service"
done
chmod 0755 "$DEST/service/scripts/"*.sh
umask 077
printf 'PETER_SIDE=%s\nCOMPOSE_PROFILES=%s\nROS_DOMAIN_ID=%s\n' \
  "$side" "$side" "$domain" > "$DEST/.env"
chmod 0600 "$DEST/.env"
# Build the installed workspace explicitly; ros_run.sh only launches the node.
docker run --rm --mount "type=bind,src=$DEST/ros,dst=/ros" \
  ros-humble-peter bash /ros/ros_build.sh --packages-select "peter_defense_$side"
systemctl daemon-reload
systemctl enable --now "peter-$side.service"
printf 'Installed and started peter-%s.service using %s\n' "$side" "$daemon"
printf 'Status: systemctl status peter-%s.service\n' "$side"
printf 'ROS logs: docker logs -f ros-peter-%s\n' "$side"
