# aris_localization

Localization package scaffold.

Priority order:

1. LiDAR.
2. IMU/Odometry.
3. Camera.
4. GPS.

V2 adds:

- ROS-free transform/error helpers in `aris_localization/localization_core.py`.
- A bounded Gazebo gpu_lidar probe: `nix develop -c just v2-lidar-smoke`.
- A launch scaffold that keeps the shared ARIS URDF as the vehicle source of truth, spawns it into
  Gazebo, bridges the simulated gpu_lidar raw cloud, and normalizes it onto `/scan_cloud`.

The current Gazebo smoke verifies that a headless `ros_gz` world can spawn the shared URDF and
publish a normalized PointCloud2 sample with the ARIS `/scan_cloud` contract:

```bash
nix develop -c just v2-lidar-smoke
```

The static Gazebo localization smoke extends that path into `lidar_localization_node`:

```bash
nix develop -c just v2-gazebo-localization-smoke
```

It verifies `/scan_cloud`, `/odometry/filtered`, and `map->odom` in one launch. It does not yet
move the vehicle.

The moving Gazebo smoke adds `gazebo_pose_sync_node`, synchronizing `/wheel_odom` into the Gazebo
ARIS entity through the Gazebo `/world/aris_lidar_smoke/set_pose` service:

```bash
nix develop -c just v2-gazebo-moving-smoke
```

This verifies that a commanded vehicle simulation movement also moves the Gazebo entity and keeps
the Gazebo gpu_lidar -> `/scan_cloud` -> localization path alive. The smoke also checks that the
front LiDAR range changes as the vehicle moves through the Gazebo target scene. Gazebo physics is
not yet the motion authority.

The Gazebo physics smoke removes pose sync from the motion path:

```bash
nix develop -c just v2-gazebo-physics-smoke
```

It sends `/cmd_drive` through the simulation HAL bridge into Gazebo's Ackermann steering plugin,
then requires `/gazebo/odom`, Gazebo `/pose/info`, and `/scan_cloud` to stay live. This is a
physics-motion gate, not a full localization acceptance test yet.

The Gazebo physics-localization smoke uses Gazebo's odometry as the localization prior:

```bash
nix develop -c just v2-gazebo-physics-localization-smoke
```

It remaps `/gazebo/odom` to the node's `/wheel_odom` input and requires `/odometry/filtered` to
follow the physics-driven ARIS entity while the gpu_lidar cloud remains live.

The recorded LiDAR bag smoke captures that same path as replayable evidence:

```bash
nix develop -c just v2-recorded-lidar-bag-smoke
```

It writes an MCAP rosbag under `$ARIS_LOGS/bags/` and validates that `/scan_cloud`,
`/gazebo/odom`, `/odometry/filtered`, `/cmd_drive`, and `/tf` all have enough recorded samples.
Run `nix develop -c just v2-lidar-bag-contract /path/to/bag` for the same metadata gate on an
operator-provided real bag.

Replay-score an accepted bag with:

```bash
nix develop -c just v2-lidar-bag-replay /path/to/bag
```

The replay gate plays the bag inside the ROS 2 container and checks that `/scan_cloud`, `/tf`,
`/cmd_drive`, `/gazebo/odom`, and `/odometry/filtered` arrive with coherent motion and bounded
filtered-vs-Gazebo pose gap. `nix develop -c just v2-recorded-lidar-replay-smoke` records a fresh
synthetic V2 bag and immediately runs that same score.

The Gazebo drift-recovery smoke uses the same gpu_lidar path as a correction source:

```bash
nix develop -c just v2-gazebo-drift-smoke
```

It synchronizes Gazebo from `/aris/sim/ground_truth`, injects lateral drift into `/wheel_odom`, and
requires `/odometry/filtered` to reduce that drift using Gazebo `/scan_cloud` observations.

This is still a V2 scaffold, not production localization. Full V2 still needs real Unitree profile
values, recorded LiDAR data, map generation, NDT/EKF selection, and hardware validation.

Mitigation path now available: `aris_vehicle_sim` provides a spec-driven 3D LiDAR surrogate that
publishes `/scan_cloud` as `sensor_msgs/PointCloud2` from a YAML LiDAR profile and 3D box map:

```bash
nix develop -c just lidar-sim-smoke
```

This does not complete V2 localization by itself. It unblocks algorithm development by giving V2/V3
the same topic/type contract that the real LiDAR driver will later provide.

V2A now adds a conservative LiDAR-localization ownership path:

```bash
nix develop -c just v2a-localization-smoke
```

The V2A launch disables the simulator's V1 `/odometry/filtered` placeholder, runs the LiDAR
surrogate, and starts `lidar_localization_node`, which publishes `/odometry/filtered` and
`map->odom`. In the current no-drift lightweight sim, the launch uses conservative correction
windows while the ROS-free scan-matching core remains tested separately with an offset correction
case.

The drift-recovery gate exercises the same ownership path with intentionally corrupted wheel
odometry:

```bash
nix develop -c just v2a-drift-smoke
```

That launch publishes ground truth only on `/aris/sim/ground_truth` for measurement and sensor
simulation, injects lateral drift into `/wheel_odom` and `odom->base_link`, and requires
LiDAR-owned `/odometry/filtered` to stay within 5 cm of ground truth while the wheel odometry
drifts by at least 8 cm.

The route-repeat gate adds `local_planner_node` back into that drift stack and verifies that V1
route following still works from localization-owned odometry:

```bash
nix develop -c just v2a-route-smoke
```

It generates a bounded straight V1 route under `/aris/data/routes/`, follows it through the
existing PurePursuit wrapper, and requires ground-truth lateral tracking under 0.3 m while the
wheel odometry drifts by at least 8 cm. The separate drift-recovery gate above keeps the tighter
5 cm localization recovery check.

`lidar_localization_node` also uses a ROS-free correction acceptance gate in
`aris_localization/fusion_gate.py`. The gate rejects scan-match corrections that have too few
points, excessive mean map error, or implausibly large translation/yaw jumps; rejected corrections
fall back to the wheel-odom pose for that update rather than poisoning `/odometry/filtered`.
