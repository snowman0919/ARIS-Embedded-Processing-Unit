FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release locales software-properties-common \
    build-essential cmake ninja-build git git-lfs pkg-config \
    python3 python3-pip python3-venv python3-pytest \
    python3-argcomplete python3-numpy python3-yaml \
    && locale-gen en_US en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

RUN set -eux; \
    add-apt-repository universe; \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
      -o /usr/share/keyrings/ros-archive-keyring.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main" \
      > /etc/apt/sources.list.d/ros2.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ros-jazzy-desktop \
      ros-jazzy-demo-nodes-cpp \
      ros-jazzy-demo-nodes-py \
      ros-jazzy-launch-testing \
      ros-jazzy-rmw-fastrtps-cpp \
      python3-rosdep \
      python3-vcstool \
      python3-colcon-common-extensions; \
    for pkg in ros-jazzy-rviz2 ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-ros-gz; do \
      apt-get install -y --no-install-recommends "$pkg" \
        || echo "WARNING: optional package $pkg unavailable for this architecture/repository snapshot"; \
    done; \
    rosdep init || true; \
    rosdep update || true; \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir \
    pytest pytest-cov ruff mypy pydantic numpy scipy

# ARIS extras not in ros-jazzy-desktop:
#  - ackermann_msgs: the /cmd_drive control contract type.
#  - teleop_twist_keyboard: V0 manual driving (keyboard -> /cmd_vel -> /cmd_drive).
# Kept as a separate late layer so the heavy desktop layer above stays cached.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-ackermann-msgs \
      ros-jazzy-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

COPY docker/ros_entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

WORKDIR /workspaces/aris
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
