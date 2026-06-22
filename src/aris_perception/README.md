# aris_perception

Simulation-first perception scaffolds for V2, V3, and V5.

No camera streams or segmentation model are available yet, so this package does not claim V3
completion. It currently contains ROS-free helpers for turning a segmentation detection plus camera
calibration/pose into a semantic map observation that `aris_mapping` can consume.

`simulated_segmentation_node` is a deterministic simulation-only source for the V3 smoke. It does
not run a real model; it emits repeat-pass observations on
`/aris/perception/semantic_observation` so the map update path can be verified without camera
assets.

`gazebo_cloud_adapter_node` is the V2 Gazebo bridge normalizer. It subscribes to the raw
Gazebo/ros_gz GPU LiDAR cloud on `/gazebo/scan_cloud` and republishes the ARIS contract topic
`/scan_cloud` with:

- `frame_id=lidar_link`
- unorganized `height=1`
- `point_step=24`
- fields `x`, `y`, `z`, `intensity`, `ring`, `time`

This keeps Gazebo simulation and the pure LiDAR surrogate behind the same downstream perception and
localization topic contract.

`dynamic_obstacle_node` is the first V5 dynamic-obstacle avoidance gate. It reads `/scan_cloud`,
filters points inside the forward driving corridor, and publishes
`/aris/perception/dynamic_obstacle` as a JSON advisory:

- `clear`: no local speed limit.
- `slow`: local planner caps speed and applies partial braking.
- `stop`: local planner commands zero speed and full braking.

The smoke gate `just v5-dynamic-obstacle-smoke` verifies that those advisories affect `/cmd_drive`
without changing the existing simulator/HAL control contract. It is still simulation evidence, not
a field-validated tracker or full dynamic replan.
