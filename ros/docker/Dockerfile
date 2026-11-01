FROM osrf/ros:humble-desktop-full
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-compressed-image-transport ros-humble-image-transport-plugins \
    python3-opencv python3-numpy python3-setuptools python3-colcon-common-extensions \
    v4l-utils gstreamer1.0-tools gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /ros
RUN printf '\nsource /opt/ros/humble/setup.bash\nif [ -f /ros/ros2_ws/install/setup.bash ]; then source /ros/ros2_ws/install/setup.bash; fi\n' >> /root/.bashrc
CMD ["bash"]
