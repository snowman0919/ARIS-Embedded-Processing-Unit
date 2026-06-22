# aris_planning

Planning package for ARIS.

Current layers:

- V1 local route following: `local_planner_node` consumes `/odometry/filtered` and publishes the
  invariant `/cmd_drive` contract through the existing PurePursuit core.
- V4 simulation global planning: `global_planner_node` builds a semantic route-graph plan,
  publishes `/global_path`, and lets `local_planner_node` follow that path without changing
  PurePursuit or `/cmd_drive`.

Simulation smoke:

```bash
nix develop -c just v4-goal-smoke
```

This verifies a semantic detour around a high-risk map cell and goal arrival in the lightweight
simulator. It is not a full Nav2 production integration.

Interactive manual demo:

```bash
# Terminal 1: start sim teleop + path recording + RViz map view.
nix develop -c just v4-teach-rviz my_route.csv

# Terminal 2: drive with the keyboard while Terminal 1 records.
nix develop -c just teleop-key

# Back in Terminal 1: press Ctrl-C when the route is done.
# Then replay that route through V2A localization + V4 global path planning + RViz.
nix develop -c just v4-follow-rviz my_route.csv
```

Recorded routes are stored under `$ARIS_DATA/routes/` on the host and `/aris/data/routes/` in the
ROS container. During follow mode, the recorded CSV is converted into a V4 route graph, published as
`/global_path`, and followed by the existing local planner.

RViz colors:

- yellow: `/aris/recorded_path`, the teach-mode path being drawn
- red: `/global_path`, the V4 global route graph path
- green: `/aris/planned_path`, the local PurePursuit path currently being followed
- blue arrow trail: `/odometry/filtered`
- point cloud: `/scan_cloud`
