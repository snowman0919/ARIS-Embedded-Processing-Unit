# Simulation

Default simulation is pure software and dry-run safe.

```bash
just sim
```

Closed-loop local planning simulation:

```bash
just auto-sim
```

Visual closed-loop simulation:

```bash
just auto-rviz
```

`just auto-rviz` displays the grid, vehicle odometry, planned path, and simulated obstacles in RViz.

The starter simulator publishes:

- `/aris/sim/odom`
- `/aris/sim/steering_state`
- `/aris/sim/obstacles`
- `/aris/sim/planned_path`

It subscribes to:

- `/aris/sim/estop`
- `/aris/sim/target_velocity`
- `/aris/sim/target_steering`
- `/aris/sim/brake`

Gazebo is optional:

```bash
just gazebo
```

Headless Gazebo LiDAR smoke:

```bash
just v2-lidar-smoke
```

This launches `ros_gz`, spawns the shared ARIS URDF, bridges the Gazebo `gpu_lidar` raw
PointCloud2, and normalizes it through `aris_perception.gazebo_cloud_adapter_node` to the standard
`/scan_cloud` contract (`frame_id=lidar_link`, fields `x/y/z/intensity/ring/time`,
`point_step=24`).

The deterministic software LiDAR surrogate remains available for algorithm development and CI-like
checks that do not need Gazebo rendering:

```bash
just lidar-sim-smoke
just scan-cloud-contract
```

Use recorded data and simulation before hardware integration.
