# V2 LiDAR Bag Replay Scoring

This gate turns an accepted V2 LiDAR rosbag into replay evidence. The metadata
contract alone proves that required topics were recorded; replay scoring proves
that the bag can be played back and still carries coherent localization motion.

## Existing Bag

Run replay scoring on an existing synthetic or operator-provided bag:

```bash
./scripts/check_v2_lidar_bag_replay.sh /path/to/bag
```

The script first runs `validate_v2_lidar_bag.py`, then mounts the bag read-only
into the ROS 2 container and plays it with `ros2 bag play`. A probe node listens
for:

- `/cmd_drive`
- `/scan_cloud`
- `/gazebo/odom`
- `/odometry/filtered`
- `/tf`

It fails if replayed clouds, odometry, or TF are missing, if the cloud frame is
not `lidar_link`, if recorded drive commands contain no moving speed samples, if
Gazebo odometry and filtered odometry do not move far enough, or if the final
filtered-vs-Gazebo pose gap exceeds the configured bound.

Useful thresholds can be tuned with environment variables:

```bash
ARIS_REPLAY_WAIT_S=20.0
ARIS_REPLAY_MIN_TOPIC_SAMPLES=5
ARIS_REPLAY_MIN_DELTA_X=0.20
ARIS_REPLAY_MAX_FINAL_X_GAP=0.50
ARIS_REPLAY_MAX_FINAL_Y_GAP=0.35
```

## Record And Replay

Run the complete synthetic recorded-data gate:

```bash
./scripts/check_v2_recorded_lidar_replay.sh
```

This records the Gazebo physics-localization path with
`check_v2_recorded_lidar_bag.sh`, finds the newly written bag under
`$ARIS_LOGS/bags`, and immediately runs replay scoring on that bag.

## Current Evidence

The first direct replay-scoring run accepted:

```text
/home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T022337Z
```

with:

```text
cmd_samples=79
cloud_samples=137
gazebo_samples=321
filtered_samples=107
tf_samples=107
gazebo_delta_x=3.101
filtered_delta_x=3.008
final_gap=(0.000,0.000)
```

This is still synthetic Gazebo evidence, not production Unitree LiDAR evidence.
Real V2 completion still requires real bag replay, map-generation acceptance,
calibrated localization settings, HIL, and field validation.

The first record-and-replay run accepted:

```text
/home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T023334Z
```

with:

```text
duration_s=13.668
messages=788
cmd_samples=63
cloud_samples=107
gazebo_samples=403
filtered_samples=107
tf_samples=108
gazebo_delta_x=2.992
filtered_delta_x=2.992
final_gap=(0.000,0.000)
```
