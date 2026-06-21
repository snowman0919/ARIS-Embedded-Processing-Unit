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
