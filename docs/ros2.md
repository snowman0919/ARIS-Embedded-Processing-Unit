# ROS2

The ROS2 container prefers ROS2 Jazzy on Ubuntu 24.04.

Included runtime goals:

- colcon, rosdep, vcstool, launch tooling.
- RViz2.
- Gazebo/ros_gz where available.
- Nav2 packages where available.
- C++ and Python development tools.

Smoke tests:

```bash
just ros2-test
just ros2-build
```

Starter packages:

- `aris_vehicle_sim`
- `aris_mcu_bridge`
- `aris_planning`
- `aris_ai_semantics`
