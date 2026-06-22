# Sensors

Primary sensor:

- Unitree L2 4D LiDAR.

Vision:

- Six synchronized USB cameras: front, front-left, front-right, left, right, rear.

Other sensors:

- GPS.
- IMU.
- Wheel encoder.
- Steering encoder.

Localization priority:

1. LiDAR.
2. IMU/Odom.
3. Camera.
4. GPS.

Device access is not part of default simulation mode. Inspect hardware with:

```bash
./scripts/check_devices.sh
```

For hardware sessions, map only the specific devices needed by that session, such as `/dev/video0`, `/dev/ttyUSB0`, `/dev/ttyACM0`, or a CAN interface.
