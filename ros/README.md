# Peter ROS workspace

ROS 2 Humble Desktop Full (Ubuntu 22.04), including compressed image transport.
Python dependencies are installed by apt in the Dockerfile to keep OpenCV's
GStreamer support and ROS's Python ABI consistent; no pip installation is needed.

From the repository root:

```bash
bash setup.sh                         # writes .env: remote or main
bash ros/docker/build.sh              # builds ros-humble-peter
bash container.sh remote start        # builds and starts ros-peter-remote
bash container.sh remote attach       # interactive shell
bash container.sh remote stop         # compose down
```

Use `main` in place of `remote` for the main side. After setup you can omit the
side (`bash container.sh start`). An optional last argument overrides the
container name; use the same override for subsequent commands. Main runs an idle
ROS shell environment without requiring a camera. Host networking enables ROS
DDS discovery on Linux; use the same ROS_DOMAIN_ID in both machines' .env files.
Only one side should be running per checkout; stop it before switching sides.
Direct Compose use: `docker compose --profile remote up -d remote` (or `main`).
The side selected by setup is used automatically by container.sh.

The ROS workspace is `/ros/ros2_ws`, with packages in `ros2_ws/src`.
The remote service builds that workspace and starts the camera node.
Build, install, and log artifacts stay inside `ros2_ws`; activation sources
`ros2_ws/install/setup.bash`, and cleaning removes those workspace artifacts.
Inside the container, available helper scripts are:

```bash
source /ros/ros_activate.sh            # activate ROS and existing overlay
bash /ros/ros_build.sh                 # colcon build --symlink-install
bash /ros/ros_run.sh                   # build package and run camera publisher
bash /ros/ros_clean.sh                 # delete build/install/log artifacts
```

Stop the running remote service before manually running another camera node.
Additional arguments to ros_build.sh go to colcon; arguments to ros_run.sh go
to the node, e.g. `--ros-args -p jpeg_quality:=85`.

The node publishes sensor_msgs/msg/CompressedImage JPEGs on
`/peter/remote/video/compressed` with best-effort sensor-data QoS. It requests
3840×2160 at 30 FPS, enables the camera's automatic exposure menu and independent
auto gain when exposed, and disables exposure frame-rate reduction when supported.
Some cameras couple gain to auto exposure and have no separate auto-gain switch;
this is reported explicitly. V4L2 MJPEG, V4L2 YUYV, then GStreamer JPEG/raw are
probed using actual frames and measured capture rate. No backend is accepted at
a lower resolution or negotiated frame rate. JPEG encoding, USB bandwidth, camera
exposure, lighting, and CPU load can still limit sustained publish throughput.

Diagnostics inside the container:

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext
v4l2-ctl -d /dev/video0 --list-ctrls-menus
ros2 topic info /peter/remote/video/compressed --verbose
ros2 topic hz /peter/remote/video/compressed
```

A camera supporting 3840×2160 at 30 FPS and suitable USB bandwidth is required.
Startup fails with diagnostics if no backend passes the probe. The Docker daemon
must be accessible to the host user; no privileged container is required.
