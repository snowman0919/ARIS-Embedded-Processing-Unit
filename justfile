set dotenv-load := true

check-host:
    ./scripts/check_host.sh

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

rviz:
    ./scripts/run_rviz.sh

auto-rviz:
    ./scripts/run_auto_rviz.sh

gazebo:
    ./scripts/run_gazebo.sh

protocol-test:
    python3 -m pytest src/aris_mcu_bridge/test tests/protocol

firmware-test:
    ./scripts/firmware_test.sh

clean:
    ./scripts/clean.sh
