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

Use recorded data and simulation before hardware integration.
