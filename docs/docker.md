# Docker

Docker provides the ROS2, AI, simulation, and embedded build runtimes.

Default services:

- `aris-ros2-dev`
- `aris-ai-dev`
- `aris-embedded-dev`

Profiles:

- `gui`: RViz/Gazebo and X11 forwarding.
- `hardware`: optional USB and serial-by-id access. Add specific `--device /dev/videoN`, `--device /dev/ttyUSBN`, `--device /dev/ttyACMN`, or CAN device mappings only for the hardware session that needs them.
- `isaac`: optional Isaac Sim image.

ROS2 uses host networking because DDS discovery commonly relies on UDP multicast. Default simulation still sets `ROS_LOCALHOST_ONLY=1`.

Do not use privileged mode for the default development containers. Hardware helpers must be separate and explicit.
