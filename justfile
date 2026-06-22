set dotenv-load := true

check-host:
    ./scripts/check_host.sh

core-readiness:
    ./scripts/check_core_readiness.sh

core-readiness-report:
    ./scripts/run_core_readiness_report.sh

nix-shell-info:
    @printf 'ARIS_WS=%s\nARIS_HOME=%s\nARIS_DATA=%s\nARIS_LOGS=%s\nARIS_MODELS=%s\nROS_DOMAIN_ID=%s\nROS_LOCALHOST_ONLY=%s\n' "$ARIS_WS" "$ARIS_HOME" "$ARIS_DATA" "$ARIS_LOGS" "$ARIS_MODELS" "$ROS_DOMAIN_ID" "$ROS_LOCALHOST_ONLY"

docker-build:
    ./scripts/docker_build.sh

gpu-test:
    ./scripts/check_gpu_container.sh

ros2-shell:
    ./scripts/run_ros2.sh

ai-shell:
    ./scripts/run_ai.sh

embedded-shell:
    ./scripts/run_embedded.sh

ros2-build:
    ./scripts/run_ros2.sh colcon build --symlink-install

ros2-test:
    ./scripts/check_ros2.sh

python-test:
    ./scripts/check_python_tests.sh

sim:
    ./scripts/check_sim.sh

auto-sim:
    ./scripts/check_autonomous_sim.sh

# V0 manual driving: bring up the sim stack in teleop mode (Ctrl-C to stop).
teleop:
    ./scripts/run_ros2.sh ros2 launch aris_bringup bringup.launch.py use_sim:=true mode:=teleop

# V0 keyboard driver: run in a second terminal to publish /cmd_vel.
teleop-key:
    ./scripts/run_ros2.sh ros2 run teleop_twist_keyboard teleop_twist_keyboard

# V0 recording: capture the contract topics to $ARIS_LOGS/bags/.
record:
    ./scripts/run_ros2.sh ros2 launch aris_bringup record.launch.py

# V1 teach mode: record /odometry/filtered to $ARIS_DATA/routes/route.csv.
path-record:
    ./scripts/run_ros2.sh ros2 launch aris_planning path_recorder.launch.py

# V1 repeat smoke: follow a synthetic route and check lateral error stays bounded.
v1-smoke:
    ./scripts/check_v1_route_repeat.sh

# V2 probe: headless Gazebo + URDF spawn + gpu_lidar bridge to /scan_cloud.
v2-lidar-smoke:
    ./scripts/check_v2_gazebo_lidar.sh

# V2 probe: Gazebo gpu_lidar -> /scan_cloud -> localization-owned odometry.
v2-gazebo-localization-smoke:
    ./scripts/check_v2_gazebo_localization.sh

# V2 probe: moving sim odom syncs Gazebo entity pose and drives gpu_lidar localization.
v2-gazebo-moving-smoke:
    ./scripts/check_v2_gazebo_moving_localization.sh

# V2 probe: /cmd_drive moves the Gazebo URDF through its Ackermann physics plugin.
v2-gazebo-physics-smoke:
    ./scripts/check_v2_gazebo_physics.sh

# V2 probe: Gazebo physics odom drives LiDAR localization without pose sync.
v2-gazebo-physics-localization-smoke:
    ./scripts/check_v2_gazebo_physics_localization.sh

# V2 recorded-data gate: capture a physics-localization LiDAR bag and validate metadata.
v2-recorded-lidar-bag-smoke:
    ./scripts/check_v2_recorded_lidar_bag.sh

# V2 recorded-data gate: capture a physics-localization LiDAR bag and replay-score it.
v2-recorded-lidar-replay-smoke:
    ./scripts/check_v2_recorded_lidar_replay.sh

# V2 recorded-data gate: validate an existing operator-provided LiDAR bag.
v2-lidar-bag-contract bag:
    ./scripts/check_v2_lidar_bag_contract.sh "{{bag}}"

# V2 recorded-data gate: replay-score an accepted operator-provided LiDAR bag.
v2-lidar-bag-replay bag:
    ./scripts/check_v2_lidar_bag_replay.sh "{{bag}}"

# V2 probe: drifted wheel odom must be corrected by Gazebo gpu_lidar observations.
v2-gazebo-drift-smoke:
    ./scripts/check_v2_gazebo_drift_recovery.sh

# V2 aggregate: run all headless Gazebo gpu_lidar localization smokes.
v2-gazebo-stack-smoke:
    ./scripts/check_v2_gazebo_stack.sh

# V2 algorithm-development sensor surrogate: spec-driven 3D LiDAR sim -> /scan_cloud.
lidar-sim-smoke:
    ./scripts/check_lidar_sim.sh

scan-cloud-contract:
    ./scripts/check_scan_cloud_contract.sh

# V2A: LiDAR surrogate + known-map scan matching owns /odometry/filtered and map->odom.
v2a-localization-smoke:
    ./scripts/check_v2a_localization.sh

# V2A correction gate: injected wheel-odom drift must be recovered by LiDAR localization.
v2a-drift-smoke:
    ./scripts/check_v2a_drift_recovery.sh

# V2A route gate: V1 route following must work on localization-owned odometry under drift.
v2a-route-smoke:
    ./scripts/check_v2a_route_repeat.sh

# V3 simulation gate: generate and validate a five-layer semantic map snapshot.
v3-semantic-smoke:
    ./scripts/check_v3_semantic_map.sh

# V4 simulation gate: semantic global path is followed to the goal.
v4-goal-smoke:
    ./scripts/check_v4_goal_nav.sh

# V5 simulation gate: dynamic obstacle advisory slows/stops the local planner.
v5-dynamic-obstacle-smoke:
    ./scripts/check_v5_dynamic_obstacle.sh

# V6 offline gate: generate advisory-only semantic review from V3 map artifacts.
v6-semantic-review-smoke:
    ./scripts/check_v6_semantic_review.sh

operator-goal-smoke:
    ./scripts/check_operator_goal.sh

# Interactive V4 demo, step 1: drive manually while recording a route CSV.
v4-teach route="manual_v4_route.csv":
    ./scripts/manual_v4_teach.sh "{{route}}"

# Interactive V4 demo with RViz, step 1: draw and see the recorded path live.
v4-teach-rviz route="manual_v4_route.csv":
    ./scripts/manual_v4_teach_rviz.sh "{{route}}"

# Interactive V4 demo, step 2: follow the recorded route through V4 global planning.
v4-follow route="manual_v4_route.csv":
    ./scripts/manual_v4_follow.sh "{{route}}"

# Interactive V4 demo with RViz, step 2: follow while visualizing map, paths, LiDAR, and TF.
v4-follow-rviz route="manual_v4_route.csv":
    ./scripts/manual_v4_follow_rviz.sh "{{route}}"

rviz:
    ./scripts/run_rviz.sh

auto-rviz:
    ./scripts/run_auto_rviz.sh

gazebo:
    ./scripts/run_gazebo.sh

protocol-test:
    python3 -m pytest src/aris_mcu_bridge/test tests/protocol

mcu-serial-loopback:
    ./scripts/check_mcu_serial_loopback.sh

firmware-test:
    ./scripts/firmware_test.sh

clean:
    ./scripts/clean.sh
