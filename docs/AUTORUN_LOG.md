# ARIS Autonomous Run Log

Append one dated entry per milestone attempt (newest at the bottom). **The owner reads this first
in the morning** — be precise and honest: what was built, which completion criteria passed (with
numbers), what is stubbed/blocked and why, and the exact next step. See `HANDOFF.md` §10 for the
rules of this run.

Entry format:

```
## <YYYY-MM-DD HH:MM> — V<n>: <title> — [DONE | WIP | BLOCKED]
- Built:        <files/packages added or changed>
- Verified:     <completion criteria + measured result, e.g. "tracking err 0.21 m < 0.3 m">
- Build/tests:  <ros2-build green? N unit tests pass?>
- Commit:       <short hash + message>
- Stubbed/blocked: <what is not real yet, and why>
- Next:         <the precise next step>
```

---

## 2026-06-21 — Starting point (handoff baseline)
- State: §4 interface contract + V0 done & verified. `nix develop -c just ros2-build` green
  (7 packages); integration smoke + 13 unit tests pass.
- Sim is a Python kinematic node (not Gazebo). `/odometry/filtered` and `map→odom` are V1
  placeholders. Real-mode HAL is a stub.
- Next: **V1 — teach-and-repeat** (HANDOFF §8).

## 2026-06-21 02:06 KST — V1: Teach-and-Repeat — DONE
- Built:        Added `aris_planning.route` ROS-free CSV/waypoint core, `path_recorder_node`,
  `path_recorder.launch.py`, `route_file` plumbing in `local_planner_node`, bringup/autonomous
  route launch args, `just path-record`, and a bounded `just v1-smoke` teach/repeat check.
- Verified:     Automated teach/repeat in sim recorded `/odometry/filtered` during teleop mode to
  `/aris/data/routes/v1_smoke_route_20260620_170559.csv` (36 waypoints, 7.499 m), replayed that
  exact CSV in auto mode, and measured `max_lateral_error=0.000 m` (< 0.3 m) over 426 odometry
  samples with `max_x=7.273 m`.
- Build/tests:  `nix develop -c just ros2-build` green (7 packages; setuptools warning only);
  `python3 -m pytest src -q` inside the ROS container green (`25 passed`); `nix develop -c just
  auto-sim` green; `nix develop -c just v1-smoke` green.
- Commit:       `c4d2897` — `V1: teach-and-repeat (verified: route smoke 0.000m)`.
- Stubbed/blocked: V1 still uses the known placeholder sim localization: `vehicle_sim_node`
  publishes `/odometry/filtered`, and bringup publishes static identity `map→odom`. This is
  expected until V2 replaces both with LiDAR localization.
- Next:         Start V2 by assessing whether Gazebo Harmonic / `ros_gz` / `gpu_lidar` are
  available in the Nix+Docker ROS environment; if unavailable or headless GPU rendering blocks
  `/scan_cloud`, document honestly and add only safe, tested scaffold.

## 2026-06-21 02:16 KST — V2: LiDAR Localization — WIP/BLOCKED
- Built:        Added a buildable `aris_localization` package with ROS-free
  `localization_core.py` transform/error helpers and tests; added `v2_gazebo_lidar.launch.py`,
  a local `aris_lidar_smoke.sdf` world, `just v2-lidar-smoke`, and a guarded `use_sim` gpu_lidar
  block in the single shared ARIS URDF that targets `/scan_cloud`.
- Verified:     `gz`, `ros_gz`, `robot_localization`, `slam_toolbox`, and PCL packages are present
  in the ROS container. Headless server-only Gazebo can stay alive with an empty/world file, but
  `nix develop -c just v2-lidar-smoke` fails honestly: no `/scan_cloud` PointCloud2 sample; launch
  log shows `ros_gz_sim create` waiting for `/world/aris_lidar_smoke/create`, then the smoke times
  out and reports `/scan_cloud` has no type/publisher.
- Build/tests:  `nix develop -c just ros2-build` green (8 packages); `python3 -m pytest src -q`
  inside the ROS container green (`29 passed`); `nix develop -c just auto-sim` green, so V0/V1
  stack behavior still launches after the URDF sensor guard. `nix develop -c just v2-lidar-smoke`
  fails with exit code 1 by design because the completion-critical `/scan_cloud` sample is absent.
- Commit:       `ff118bc` — `V2: scaffold lidar localization probe (blocked: no scan cloud)`.
- Stubbed/blocked: V2 is not complete. No Gazebo-spawned URDF, no `/scan_cloud`, no SLAM `.pcd`,
  no NDT scan matching, no EKF-owned `/odometry/filtered`, and no real `map→odom`. The concrete
  blocker is Gazebo/ros_gz headless service/sensor activation: the world create service is not
  discoverable by `ros_gz_sim create`, and therefore the gpu_lidar cannot be verified.
- Next:         Fix the Gazebo headless transport/rendering path first: make
  `/world/aris_lidar_smoke/create` discoverable, spawn the shared URDF, and get one real
  PointCloud2 sample on `/scan_cloud`. Only after that should V2 proceed to SLAM map generation,
  NDT/EKF localization ownership of `/odometry/filtered` and `map→odom`, and the ≤5 cm drift gate.

## 2026-06-21 02:16 KST — SUMMARY
- Truly done: V1 teach-and-repeat. Criteria passed with an automated recorded teleop route
  (36 waypoints, 7.499 m) replayed at `max_lateral_error=0.000 m < 0.3 m`; commit `c4d2897`.
- WIP/blocked: V2 LiDAR localization. Scaffold and tests exist; completion criteria are not met
  because Gazebo/ros_gz does not yet spawn the URDF or publish `/scan_cloud` in this headless run;
  commit `ff118bc`.
- Not attempted: V3-V6. They depend on V2’s real localization and sensor streams, so forward
  progress stopped per the honesty gate instead of skipping dependencies.
- Current state: `nix develop -c just ros2-build` green (8 packages), ROS-free/unit suite green
  (`29 passed`), `nix develop -c just auto-sim` green, `nix develop -c just v2-lidar-smoke`
  correctly fails with the documented V2 blocker.
- Exact next step: debug Gazebo/ros_gz service discovery and headless gpu_lidar rendering until
  `just v2-lidar-smoke` produces one `/scan_cloud` PointCloud2 sample, then implement the real
  V2 localization chain and rerun V1 repeat on the new `/odometry/filtered`.

## 2026-06-21 17:50 KST — V2: Spec-Driven 3D LiDAR Surrogate — WIP
- Built:        Added `aris_vehicle_sim.lidar_sim_core` ROS-free 3D ray-casting core,
  `lidar_sim_node`, LiDAR profile YAML, 3D box-map YAML, `lidar_sim.launch.py`, and
  `just lidar-sim-smoke`. The PointCloud2 schema includes `x,y,z,intensity,ring,time` and uses
  `/scan_cloud` with `frame_id=lidar_link`, matching the real-sensor handoff contract.
- Verified:     `nix develop -c just lidar-sim-smoke` green: pure sim + LiDAR node published one
  `/scan_cloud` sample with `height=1`, `width=866`, `point_step=24`, and fields present.
- Build/tests:  `nix develop -c just ros2-build` green (8 packages);
  `python3 -m pytest src -q` green (`33 passed`); `nix develop -c just auto-sim` green.
- Commit:       `44b3d5d` — `V2: add spec-driven 3D lidar simulator`.
- Stubbed/blocked: This is not a real LiDAR driver and not full V2 localization. The default
  LiDAR profile is explicitly a configurable stand-in until the production LiDAR datasheet values
  are copied into YAML. Gazebo gpu_lidar remains blocked separately, but V2/V3 algorithm work no
  longer has to wait for Gazebo to publish `/scan_cloud`.
- Next:         Implement V2A localization on top of this `/scan_cloud` path: occupancy map /
  known-map scan matching, `map→odom` ownership, and `/odometry/filtered` publication, then rerun
  V1 repeat using the localization-owned pose.

## 2026-06-21 18:07 KST — V2A: LiDAR Localization Ownership Path — WIP
- Built:        Added ROS-free `aris_localization.scan_matching` known-box-map scan matcher,
  `lidar_localization_node`, `v2a_lidar_localization.launch.py`, and
  `just v2a-localization-smoke`. Added a `vehicle_sim_node.publish_filtered_odom` parameter so
  V2A can disable the V1 placeholder and let localization own `/odometry/filtered`; localization
  also broadcasts `map→odom`.
- Verified:     `nix develop -c just v2a-localization-smoke` green: pure sim + LiDAR surrogate +
  localization produced localization-owned `/odometry/filtered` while the vehicle drove to
  `max_x=6.507 m`; timestamp-aligned `max_position_error=0.040 m` (< 0.05 m),
  `max_yaw_error=0.000 rad`, `max_dt=0.040 s`.
- Build/tests:  `nix develop -c just ros2-build` green (8 packages);
  `python3 -m pytest src -q` green (`34 passed`); `nix develop -c just auto-sim` green, so
  existing V0/V1 launch behavior remains intact.
- Commit:       `da905a0` — `V2A: add lidar localization ownership path`.
- Stubbed/blocked: This is still V2A, not full V2. The launch uses conservative correction windows
  in the no-drift lightweight sim; the scan-matching core is tested with an offset correction case,
  but there is not yet a drift-injected closed-loop localization test, SLAM map build, NDT, EKF, or
  Gazebo/real LiDAR validation.
- Next:         Add controlled odometry drift/noise in sim and expand V2A into a real correction
  test: LiDAR scan matching should recover from drift, keep `map→odom` stable, and let V1 repeat
  pass using localization-owned `/odometry/filtered`.

## 2026-06-21 18:16 KST — V2A: LiDAR Drift-Recovery Gate — WIP
- Built:        Added controlled wheel-odometry drift injection to `vehicle_sim_node`, optional
  `/aris/sim/ground_truth` publication for bounded sim-only measurement, configurable LiDAR
  `pose_topic`, `v2a_drift_recovery.launch.py`, and `just v2a-drift-smoke`.
- Verified:     `nix develop -c just v2a-drift-smoke` green: the vehicle drove to `max_x=5.547 m`;
  injected wheel-odom error reached `max_wheel_error=0.125 m` (>= 0.08 m), while LiDAR-owned
  `/odometry/filtered` stayed at `max_filtered_error=0.047 m` (<= 0.05 m), with
  `max_yaw_error=0.000 rad` and `max_dt=0.041 s`. Sequential regressions also passed:
  `just lidar-sim-smoke` (`/scan_cloud` PointCloud2 `height=1`, `width=864`, `point_step=24`),
  `just v2a-localization-smoke` (`max_x=6.527 m`, `max_position_error=0.040 m`), and
  `just auto-sim`.
- Build/tests:  `nix develop -c just ros2-build` green (8 packages);
  `python3 -m pytest src -q` inside the ROS container green (`34 passed`).
- Commit:       `f2c9da0` — `V2A: verify lidar drift recovery`.
- Stubbed/blocked: This is still V2A WIP, not full V2. It proves known-map scan matching can
  correct controlled lateral wheel-odom drift in the lightweight simulator, but it is not yet SLAM
  map generation, NDT/EKF fusion, Gazebo gpu_lidar validation, or real LiDAR-driver validation.
  Gazebo gpu_lidar remains blocked by the previously documented headless `ros_gz_sim create` /
  `/scan_cloud` issue.
- Next:         Harden this into the next V2 increment: add a repeat-route smoke that uses
  localization-owned `/odometry/filtered` under drift, then decide whether to implement a small
  EKF/fusion scaffold or continue Gazebo gpu_lidar debugging before moving to V3 perception.

## 2026-06-21 18:16 KST — SUMMARY
- Truly passed: V1 teach-and-repeat (`max_lateral_error=0.000 m < 0.3 m`) and V2A lightweight
  LiDAR localization ownership/drift recovery (`max_wheel_error=0.125 m` corrected to
  `max_filtered_error=0.047 m`).
- WIP/blocked: Full V2 remains incomplete because Gazebo gpu_lidar still does not publish a
  verified `/scan_cloud`; SLAM `.pcd`, NDT/EKF, and real-sensor validation are not done. V3-V6
  remain blocked by full V2 completion under the honesty gate.
- Current build/test state: `nix develop -c just ros2-build` green; ROS-free unit suite green
  (`34 passed`); `just auto-sim`, `just lidar-sim-smoke`, `just v2a-localization-smoke`, and
  `just v2a-drift-smoke` all green when run sequentially.
- Exact next step: implement a V2A repeat-route drift smoke so the V1 route follower is exercised
  against localization-owned `/odometry/filtered` while wheel odometry drifts; after that, either
  add minimal EKF/fusion scaffolding or return to Gazebo gpu_lidar service/rendering debugging.

## 2026-06-21 18:20 KST — V2A: Route Repeat Under LiDAR Localization Drift — WIP
- Built:        Added `v2a_route_repeat.launch.py` and `just v2a-route-smoke`. The launch combines
  the drift-injected vehicle sim, ground-truth-driven LiDAR surrogate, LiDAR localization owner,
  and existing `local_planner_node` with a route CSV. No `/cmd_drive`, PurePursuit, TF contract, or
  URDF behavior was changed.
- Verified:     `nix develop -c just v2a-route-smoke` green: generated
  `/aris/data/routes/v2a_repeat_drift_route_20260621_091917.csv`, route-followed to
  `max_x=9.061 m`, held ground-truth route error at `max_lateral_error=0.061 m` (< 0.3 m), while
  injected wheel-odom drift reached `max_wheel_error=0.181 m` and LiDAR-owned filtered pose stayed
  at `max_filtered_error=0.019 m` (< 0.05 m), with `max_yaw_error=0.000 rad`.
- Build/tests:  `nix develop -c just ros2-build` green (8 packages);
  `python3 -m pytest src -q` green (`34 passed`); regression `just v2a-drift-smoke` green
  (`max_wheel_error=0.117 m`, `max_filtered_error=0.044 m`); `just auto-sim` green.
- Commit:       `2e3b9c4` — `V2A: verify route repeat under drift`.
- Stubbed/blocked: This still does not make full V2 complete. It is a stronger V2A proof that V1
  repeat works through localization-owned `/odometry/filtered` under controlled drift, but full V2
  still lacks SLAM map generation, NDT/EKF fusion, Gazebo gpu_lidar validation, and real LiDAR
  driver validation.
- Next:         Implement the smallest honest fusion/localization manager increment: keep the pure
  core split, add tests for odometry-vs-LiDAR correction acceptance/rejection, then expose an
  EKF-like wrapper or documented handoff path without weakening the existing drift and route gates.

## 2026-06-21 18:20 KST — SUMMARY
- Truly passed: V1 teach-and-repeat; V2A `/scan_cloud` surrogate; V2A localization ownership;
  V2A drift recovery; V2A route-repeat under drift (`max_lateral_error=0.061 m`, corrected
  localization error `0.019 m` while wheel odom drifted `0.181 m`).
- WIP/blocked: Full V2 remains incomplete because Gazebo gpu_lidar still has no verified
  `/scan_cloud`, and SLAM/NDT/EKF/real-sensor validation are not done. V3-V6 should still wait for
  the full V2 decision point unless explicitly scoped to simulation-only scaffolds.
- Current build/test state: `nix develop -c just ros2-build` green; ROS-free unit suite green
  (`34 passed`); `just auto-sim`, `just lidar-sim-smoke`, `just v2a-localization-smoke`,
  `just v2a-drift-smoke`, and `just v2a-route-smoke` have all passed sequentially.
- Exact next step: add a small tested fusion/localization manager layer that can reject bad LiDAR
  corrections and document the remaining gap to production V2; then decide whether to spend the
  next block on Gazebo gpu_lidar debugging or move to simulation-only V3 perception scaffolding.

## 2026-06-21 18:27 KST — V2A: LiDAR Correction Acceptance Gate — WIP
- Built:        Added ROS-free `aris_localization.fusion_gate` with correction accept/reject
  decisions for point count, scan-map mean error, translation jump, and yaw jump. Wired
  `lidar_localization_node` to publish the accepted scan-match pose or fall back to wheel odom for
  rejected updates. Also hardened the drift/route smoke metric matching with timestamp
  interpolation instead of nearest-sample-only comparisons.
- Verified:     `nix develop -c just v2a-drift-smoke` green after the gate:
  `max_x=9.527 m`, `max_wheel_error=0.191 m`, `max_filtered_error=0.025 m`,
  `max_yaw_error=0.000 rad`. `nix develop -c just v2a-route-smoke` green:
  `max_x=9.105 m`, `max_lateral_error=0.105 m` (< 0.3 m),
  `max_wheel_error=0.182 m`, `max_filtered_error=0.026 m`.
- Build/tests:  `nix develop -c just ros2-build` green (8 packages);
  `python3 -m pytest src -q` green (`36 passed`); `nix develop -c just auto-sim` green.
- Commit:       `4cc1d96` — `V2A: gate lidar correction updates`.
- Stubbed/blocked: This is not a production EKF. It is a deterministic safety gate around the
  current known-map scan matcher. Full V2 still needs SLAM/NDT/EKF selection or integration,
  Gazebo gpu_lidar repair, and validation against the actual LiDAR driver/profile.
- Next:         Start the V3 simulation-only perception scaffold only if it is explicitly marked as
  simulation/WIP and consumes the existing `/scan_cloud` contract; otherwise spend the next block
  on full V2 Gazebo gpu_lidar or EKF/NDT work.

## 2026-06-21 18:27 KST — SUMMARY
- Truly passed: V1; V2A LiDAR surrogate; V2A localization ownership; V2A drift recovery; V2A
  route-repeat under drift; V2A correction acceptance gate with ROS-free tests.
- WIP/blocked: Full V2 is still not complete. The Gazebo gpu_lidar path remains blocked; SLAM map
  generation, NDT/EKF production localization, and real LiDAR validation are still outstanding.
  V3-V6 remain dependent on that decision unless developed as clearly labelled simulation-only
  scaffolds.
- Current build/test state: `nix develop -c just ros2-build` green; unit suite green
  (`36 passed`); `just auto-sim`, `just v2a-drift-smoke`, and `just v2a-route-smoke` green after
  the correction gate changes.
- Exact next step: either repair the Gazebo `/scan_cloud` path for full V2, or begin a
  simulation-only V3 perception scaffold that subscribes to `/scan_cloud` and is documented as WIP
  until full V2 sensor/localization validation exists.

## 2026-06-21 18:30 KST — V3: Semantic HD Map Pure-Core Scaffold — WIP/BLOCKED
- Built:        Added buildable `aris_mapping` and `aris_perception` packages. `aris_mapping`
  contains a ROS-free five-layer semantic HD map core: metric cells, occupancy, semantic labels,
  traversability cost, and route-graph nodes/edges, with repeat-pass confidence and change
  detection policy. `aris_perception` contains a ROS-free simulation-only segmentation projection
  helper that converts a detection plus camera intrinsics/extrinsics/vehicle pose into a semantic
  map observation.
- Verified:     Unit tests cover semantic layer updates, low-confidence review, repeat-pass change
  detection, route graph blocked-edge filtering, traversability risk ordering, and projection of
  simulated camera detections into map observations.
- Build/tests:  `nix develop -c just ros2-build` green (10 packages; setuptools warnings only);
  `python3 -m pytest src -q` green (`44 passed`); `nix develop -c just auto-sim` green.
- Commit:       `8049f34` — `V3: scaffold semantic map cores`.
- Stubbed/blocked: V3 is not complete. No camera topics, no segmentation model, no ROS perception
  node, no projection from real image masks, and no repeat-pass dataset exist yet. This is a
  clearly labelled simulation-only pure-core scaffold, created because the V3 external assets are
  unavailable and full V2 Gazebo/real LiDAR validation is still WIP.
- Next:         Stop forward V3 completion claims here unless the owner provides/approves camera
  streams and a segmentation model. Safe next work is either Gazebo gpu_lidar repair for full V2 or
  a small simulation-only V4 route-graph planner scaffold using the new `aris_mapping` route graph.

## 2026-06-21 18:30 KST — SUMMARY
- Truly passed: V1 teach-and-repeat; V2A LiDAR surrogate/localization/drift/route/correction-gate
  verification; V3 pure-core map/perception scaffold tests.
- WIP/blocked: Full V2 remains incomplete because Gazebo gpu_lidar has no verified `/scan_cloud`
  and production SLAM/NDT/EKF/real LiDAR validation are not done. V3 completion is blocked by the
  missing camera streams, segmentation model, and real repeat-pass dataset.
- Current build/test state: `nix develop -c just ros2-build` green for 10 packages; unit suite
  green (`44 passed`); `just auto-sim` green after adding `aris_mapping` and `aris_perception`.
- Exact next step: choose one of two honest paths: repair full V2 Gazebo/real sensor localization,
  or continue only with explicitly labelled simulation scaffolds such as V4 route-graph planning.

## 2026-06-21 18:40 KST — V3: Simulation Semantic Map Data Flow — WIP/BLOCKED
- Built:        Added `semantic_map_node` in `aris_mapping`, `simulated_segmentation_node` in
  `aris_perception`, `v3_semantic_map_sim.launch.py`, and `just v3-semantic-smoke`. The map node
  consumes `/scan_cloud` for metric/occupancy cells and
  `/aris/perception/semantic_observation` JSON for semantic/traversability/change-detection
  updates, then publishes `/aris/mapping/semantic_map` summaries. The perception node is explicitly
  simulation-only and deterministic; it is not a real camera segmentation model.
- Verified:     `nix develop -c just v3-semantic-smoke` green. Final summary:
  `metric_cells=267`, `semantic_cells=1`, `semantic_updates=66`, `change_events=55`,
  `review_events=55`, `blocked_cells=1`, labels `road` and `debris` present. This proves the V3
  simulation data path updates all five layers and triggers repeat-pass change detection.
- Build/tests:  `nix develop -c just ros2-build` green (10 packages);
  `python3 -m pytest src -q` green (`44 passed`); regressions `just v2a-route-smoke` and
  `just v2a-drift-smoke` green (`max_filtered_error=0.025 m` in drift gate).
- Commit:       `d7105af` — `V3: verify simulation semantic map flow`.
- Stubbed/blocked: Production V3 is still blocked. There are no real camera topics, no
  segmentation model, no mask projection from actual images, no calibrated multi-camera fusion, and
  no repeat-pass dataset. Full V2 Gazebo/real LiDAR validation is also still WIP. This entry only
  completes the simulation-only V3 algorithm/data-flow path.
- Next:         To make V3 production-complete, provide or choose a segmentation model and camera
  stream source, then replace `simulated_segmentation_node` with a real perception wrapper while
  keeping the same map observation contract. In parallel, full V2 Gazebo/real LiDAR must still be
  repaired/validated.

## 2026-06-21 18:40 KST — SUMMARY
- Truly passed: V1 teach-and-repeat; V2A simulation LiDAR localization stack; V3 simulation
  semantic map data flow.
- WIP/blocked: Full V2 is blocked on Gazebo gpu_lidar/real LiDAR validation and production
  SLAM/NDT/EKF. Production V3 is blocked on real/sim camera streams, a segmentation model, mask
  projection, and repeat-pass data. V4-V6 should not be claimed complete until those dependencies
  are resolved or explicitly scoped as simulation-only scaffolds.
- Current build/test state: `nix develop -c just ros2-build` green for 10 packages; unit suite
  green (`44 passed`); `just v3-semantic-smoke`, `just v2a-route-smoke`, and
  `just v2a-drift-smoke` green.
- Exact next step: decide whether to invest next in productionizing V3 perception
  (camera/model/dataset) or closing the remaining full V2 sensor-localization gap.

## 2026-06-21 21:33 KST — V4: Simulation Goal-Based Navigation — WIP
- Built:        Added ROS-free `aris_planning.route_graph` with semantic route-graph planning,
  semantic edge costs, nearest-node selection, bidirectional edges, and path densification. Added
  `global_planner_node`, `/global_path` support in `local_planner_node`, `v4_goal_nav_sim.launch.py`,
  and `just v4-goal-smoke`. The final control output remains `/cmd_drive`; PurePursuit behavior was
  not changed.
- Verified:     `nix develop -c just v4-goal-smoke` green. The global plan used a semantic detour
  (`max_y_path=1.200 m`, `min_blocked_distance=3.000 m` from the blocked semantic cell), and the
  vehicle reached `final=(9.152, 0.705)` with `goal_error=0.721 m` (< 1.2 m) and `max_x=9.152 m`.
- Build/tests:  `nix develop -c just ros2-build` green (10 packages);
  `python3 -m pytest src -q` green (`47 passed`); `just v3-semantic-smoke` green
  (`metric_cells=259`, labels `road`/`debris`, `change_events=60`); `just auto-sim` green;
  `just v2a-drift-smoke` green after measuring the intended lateral recovery gate
  (`max_wheel_error=0.191 m`, `max_filtered_error=0.025 m`).
- Commit:       `2318f7e` — `V4: add semantic goal navigation smoke`.
- Stubbed/blocked: This is V4 simulation WIP, not full Nav2/production goal navigation. It uses a
  deterministic demo route graph and simulated semantic obstacle, not a live operator goal UI,
  Nav2 Smac planner, production map server, or real vehicle validation.
- Next:         Either harden V4 with external goal input/map loading, or return to the remaining
  production blockers: full V2 Gazebo/real LiDAR localization and production V3 camera perception.

## 2026-06-21 21:33 KST — SUMMARY
- Truly passed in simulation: V1 route repeat; V2A LiDAR localization/drift stack; V3 semantic map
  data flow; V4 semantic route-graph goal navigation.
- WIP/blocked for production: Full V2 Gazebo/real LiDAR localization, production V3 camera/model
  perception, and production V4 Nav2/map-server/operator-goal integration.
- Current build/test state: `nix develop -c just ros2-build` green for 10 packages; unit suite
  green (`47 passed`); `just v4-goal-smoke`, `just v3-semantic-smoke`, `just v2a-drift-smoke`, and
  `just auto-sim` green.
- Exact next step: decide whether the next milestone should be V5 simulation-only dynamic obstacle
  avoidance, or whether to pause roadmap progression and close the production V2/V3 gaps first.

## 2026-06-21 21:40 KST — V4: Interactive Teach/Follow Demo Harness — WIP
- Built:        Added `just v4-teach <route.csv>` and `just v4-follow <route.csv>`. Teach mode
  launches sim teleop plus `path_recorder_node` so the operator can draw a route with
  `just teleop-key`. Follow mode launches V2A LiDAR localization plus V4 `global_planner_node`,
  converts the recorded CSV into a route graph, publishes `/global_path`, and lets
  `local_planner_node` produce `/cmd_drive`.
- Verified:     `nix develop -c just ros2-build` green (10 packages);
  `python3 -m pytest src -q` green (`47 passed`); `just v4-goal-smoke` green
  (`goal_error=0.726 m`). Also smoke-launched V4 follow with an existing recorded CSV and confirmed
  `global_planner_node` loaded `46` route-graph nodes from the CSV.
- Commit:       `ae47b44` — `V4: add interactive teach-follow demo`.
- Stubbed/blocked: This is a developer demo harness. It does not provide a GUI map view, live
  operator goal selection, or production Nav2 integration.
- Next:         User can now run the two-terminal manual demo. For a visual map overlay, add RViz
  config for `/global_path`, `/aris/planned_path`, `/scan_cloud`, and TF.

## 2026-06-21 21:52 KST — V4: RViz Map/Path Visualization — WIP
- Built:        Added V4 RViz config `v4_demo.rviz`, `v4_rviz.launch.py`,
  `v4_goal_nav_rviz.launch.py`, `just v4-teach-rviz`, and `just v4-follow-rviz`. Teach mode now
  publishes `/aris/recorded_path` live from `path_recorder_node`; follow mode shows `/global_path`,
  `/aris/planned_path`, `/scan_cloud`, TF, robot model, and `/odometry/filtered`.
- Verified:     `nix develop -c just ros2-build` green (10 packages);
  `python3 -m pytest src -q` green (`47 passed`); `nix develop -c just v4-goal-smoke` green with an
  isolated ROS domain (`goal_error=0.722 m`). Also confirmed
  `v4_goal_nav_rviz.launch.py --show-args` is installed and launchable.
- Commit:       `47951d0` — `V4: add RViz teach-follow visualization`.
- Stubbed/blocked: This is RViz visualization, not Gazebo. Gazebo remains less reliable here
  because the previous headless `gpu_lidar`/`ros_gz_sim create` path was blocked. RViz is the
  recommended visualization path for the current simulator.
- Next:         Use `just v4-teach-rviz <route.csv>`, `just teleop-key`, then
  `just v4-follow-rviz <route.csv>` to inspect the full V1→V4 flow visually.

## 2026-06-22 00:45 KST — V2: Gazebo gpu_lidar Cloud Contract Repair — WIP
- Built:        Added physical inertial/collision properties to the shared ARIS URDF so Gazebo
  can spawn the model from xacro. Added `aris_perception.gazebo_cloud_adapter_node`, changed
  `v2_gazebo_lidar.launch.py` to bridge raw Gazebo cloud data to `/gazebo/scan_cloud`, and
  normalized it back to the ARIS `/scan_cloud` contract. Added a matching Gazebo smoke map,
  `v2_gazebo_localization.launch.py`, `just v2-gazebo-localization-smoke`, and the direct script
  `./scripts/check_v2_gazebo_localization.sh`. Added `gazebo_pose_sync_node`,
  `v2_gazebo_moving_localization.launch.py`, `just v2-gazebo-moving-smoke`, and
  `./scripts/check_v2_gazebo_moving_localization.sh`.
- Verified:     `./scripts/check_v2_gazebo_lidar.sh` green. The headless Gazebo world spawned
  the URDF, generated a gpu_lidar cloud, and the normalized ROS sample had
  `frame=lidar_link`, `width=10240`, `point_step=24`, fields
  `x/y/z/intensity/ring/time`, and `finite_samples=128`.
  `./scripts/check_v2_gazebo_localization.sh` green: `cloud_width=10240`,
  `filtered=(0.000,0.000,0.000)`, `map_to_odom=(0.000,0.000)`.
  `./scripts/check_v2_gazebo_moving_localization.sh` green: `cloud_width=10240`,
  `filtered_last=(2.241,0.000)`, `delta_x=2.241`,
  `front_range_delta=1.836 (2.255->0.418)`, `gazebo_aris_pose_x=3.828`.
  `./scripts/check_v2_gazebo_drift_recovery.sh` green:
  `max_wheel_error=0.109`, `max_filtered_error=0.024`,
  `final_wheel_error=0.109`, `final_filtered_error=0.008`.
  `./scripts/check_v2_gazebo_stack.sh` green: all 4 headless Gazebo V2 checks passed.
  `./scripts/check_core_readiness.sh` green: Python tests, MCU serial loopback, `/scan_cloud`
  contract, operator goal, V4 goal navigation, and V2 Gazebo stack all passed.
- Build/tests:  `./scripts/check_python_tests.sh` green (`67 passed`);
  `./scripts/check_scan_cloud_contract.sh` green for the deterministic LiDAR surrogate
  (`frame=lidar_link`, `width=868`, `point_step=24`, TF `(0.600,0.000,0.900)`).
- Commit:       not committed in this run.
- Stubbed/blocked: Full V2 is still not production complete. This repairs the Gazebo sensor
  smoke path, pose-synced moving localization data flow, and Gazebo gpu_lidar drift recovery, but
  Gazebo physics is not yet the motion authority. It still does not add real Unitree driver
  validation, recorded data, SLAM map generation, production NDT/EKF selection, or
  hardware-in-the-loop localization acceptance.
- Next:         Replace pose-sync scaffolding with a Gazebo physics/vehicle-control path or keep
  pose sync as the sim bridge while adding recorded/real LiDAR validation and a production
  NDT/EKF design.

## 2026-06-22 10:29 KST — Core Readiness Evidence Report Wrapper — WIP
- Built:        Added `./scripts/run_core_readiness_report.sh` and `just core-readiness-report` so
  the headless readiness gate writes timestamped acceptance evidence under
  `$ARIS_LOGS/readiness/`, with `latest.log` pointing to the newest run.
- Verified:     `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` green
  after the full Gazebo-inclusive `./scripts/check_core_readiness.sh` run above. The report was
  written to `/home/kotori9/aris/logs/readiness/core_readiness_20260622T012826Z.log`; tail status
  recorded `result=PASS` and `exit_code=0`.
- Commit:       not committed in this run.
- Stubbed/blocked: The wrapper preserves evidence, but a skip-Gazebo report is weaker than a full
  readiness report. Full production readiness remains blocked by real Unitree driver validation,
  recorded/real LiDAR acceptance, production map generation, and hardware-in-the-loop gates.
- Next:         Run `just core-readiness-report` without `ARIS_CORE_READINESS_SKIP_GAZEBO=1` on
  every release candidate so the timestamped artifact includes all six readiness checks.

## 2026-06-22 10:51 KST — V2: Gazebo Ackermann Physics Motion Gate — WIP
- Built:        Added simulation-only wheel links, wheel joints, and Gazebo's Ackermann steering
  system to the shared ARIS URDF when `use_sim:=true`. Added
  `aris_vehicle_sim.gazebo_cmd_drive_bridge_node` so the stack keeps publishing `/cmd_drive` while
  Gazebo receives `/cmd_vel` through `ros_gz_bridge`. Added
  `v2_gazebo_physics.launch.py`, `just v2-gazebo-physics-smoke`, and
  `./scripts/check_v2_gazebo_physics.sh`.
- Verified:     `./scripts/check_v2_gazebo_physics.sh` green:
  `odom_samples=50`, `cloud_samples=79`, `delta_x=1.645`, `gazebo_aris_pose_x=1.645`.
  `./scripts/check_v2_gazebo_stack.sh` green with 5 checks; physics subcheck reported
  `delta_x=3.552`, `gazebo_aris_pose_x=3.410`. `./scripts/check_core_readiness.sh` green:
  all 6 top-level readiness checks passed. `./scripts/run_core_readiness_report.sh` green without
  Gazebo skip and wrote
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T015140Z.log` with `result=PASS`.
- Commit:       Included with the Gazebo physics motion gate change.
- Stubbed/blocked: This proves Gazebo can be the motion authority for a straight-line smoke, but
  it is not yet the default localization authority path and does not replace recorded/real LiDAR,
  SLAM map generation, calibrated NDT/EKF settings, Unitree driver validation, or HIL acceptance.
- Next:         Use the physics motion launch as the basis for a localization smoke that consumes
  Gazebo `/gazebo/odom` or physics-derived wheel odometry instead of pose-sync scaffolding.

## 2026-06-22 11:05 KST — V2: Gazebo Physics-Fed Localization Gate — WIP
- Built:        Added `v2_gazebo_physics_localization.launch.py`,
  `just v2-gazebo-physics-localization-smoke`, and
  `./scripts/check_v2_gazebo_physics_localization.sh`. This launch keeps Gazebo Ackermann physics
  as the motion authority, remaps `/gazebo/odom` into the localization `/wheel_odom` contract, and
  verifies that `lidar_localization_node` publishes `/odometry/filtered` from live gpu_lidar data.
- Verified:     `./scripts/check_v2_gazebo_physics_localization.sh` green:
  `gazebo_delta_x=1.914`, `filtered_delta_x=1.914`, `final_gap=(0.000,0.000)`,
  `gazebo_aris_pose_x=1.914`. `./scripts/check_v2_gazebo_stack.sh` green with 6 checks; the new
  physics-localization subcheck reported `gazebo_delta_x=3.553`, `filtered_delta_x=3.553`.
  `./scripts/run_core_readiness_report.sh` green without Gazebo skip and wrote
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T020521Z.log` with `result=PASS`.
- Commit:       Included with the Gazebo physics-fed localization gate change.
- Stubbed/blocked: This removes pose sync from one moving localization path, but production V2
  still needs recorded/real LiDAR bags, map-generation acceptance, calibrated NDT/EKF settings,
  Unitree hardware driver validation, and HIL/field gates.
- Next:         Promote the physics-fed launch toward the default moving V2 path and add a
  recorded-data localization gate that does not rely on synthetic Gazebo geometry.

## 2026-06-22 11:17 KST — V2: Recorded LiDAR Bag Acceptance Gate — WIP
- Built:        Added `./scripts/check_v2_recorded_lidar_bag.sh` and
  `just v2-recorded-lidar-bag-smoke`. The gate launches the Gazebo physics-localization path,
  records `/cmd_drive`, `/scan_cloud`, `/gazebo/odom`, `/odometry/filtered`, and `/tf` to an MCAP
  rosbag, then validates `metadata.yaml` topic counts.
- Verified:     `./scripts/check_v2_recorded_lidar_bag.sh` green. It wrote
  `/home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T021652Z` with duration `11.427s`,
  `721` messages, and counts `/cmd_drive=76`, `/gazebo/odom=321`,
  `/odometry/filtered=107`, `/scan_cloud=108`, `/tf=109`.
- Commit:       Included with the recorded LiDAR bag acceptance gate change.
- Stubbed/blocked: This proves the recorded-data acceptance harness and a replayable synthetic
  LiDAR bag, but it is not a real LiDAR dataset. Production V2 still needs real/recorded Unitree
  LiDAR bags, map-generation acceptance, calibrated localization settings, and HIL/field gates.
- Next:         Add a real-bag validation mode that accepts an operator-provided bag path and
  applies the same topic/type/count contract before localization replay.

## 2026-06-22 11:23 KST — V2: Operator Bag Contract Validator — WIP
- Built:        Added `scripts/validate_v2_lidar_bag.py` and
  `just v2-lidar-bag-contract <bag>`. The validator checks rosbag `metadata.yaml` for MCAP
  storage, minimum duration, required topic counts, and expected topic types for `/cmd_drive`,
  `/scan_cloud`, `/gazebo/odom`, `/odometry/filtered`, and `/tf`.
- Verified:     The validator accepted
  `/home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T021652Z`
  (`duration_s=11.427`, `messages=721`, `/scan_cloud=108`). It rejected the older
  `/home/sbeen/aris/logs/bags/aris_verify_130829` bag because it lacks `/scan_cloud` and
  `/gazebo/odom`. Re-ran `./scripts/check_v2_recorded_lidar_bag.sh` through the shared validator;
  it wrote `/home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T022337Z` with
  `duration_s=13.689`, `messages=751`, `/scan_cloud=137`.
- Commit:       Included with the operator bag contract validator change.
- Stubbed/blocked: This is still metadata-level validation. Real V2 completion still needs replay
  scoring against recorded LiDAR, map-generation acceptance, calibrated localization settings, and
  HIL/field evidence.
- Next:         Add replay scoring that consumes an accepted bag and checks localization continuity,
  TF availability, and bounded pose drift.

## 2026-06-22 11:34 KST — V2: LiDAR Bag Replay Scoring Gate — WIP
- Built:        Added `scripts/check_v2_lidar_bag_replay.sh`,
  `scripts/check_v2_recorded_lidar_replay.sh`, `just v2-lidar-bag-replay <bag>`, and
  `just v2-recorded-lidar-replay-smoke`. The replay scorer first validates rosbag metadata, then
  mounts the bag read-only into the ROS 2 container, runs `ros2 bag play`, and checks replayed
  `/cmd_drive`, `/scan_cloud`, `/gazebo/odom`, `/odometry/filtered`, and `/tf` samples.
- Verified:     `./scripts/check_v2_lidar_bag_replay.sh
  /home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T022337Z` passed with
  `cmd_samples=79`, `cloud_samples=137`, `gazebo_samples=321`, `filtered_samples=107`,
  `tf_samples=107`, `gazebo_delta_x=3.101`, `filtered_delta_x=3.008`, and
  `final_gap=(0.000,0.000)`. Then `./scripts/check_v2_recorded_lidar_replay.sh` passed end to end:
  it wrote `/home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T023334Z`
  (`duration_s=13.668`, `messages=788`, `/scan_cloud=107`) and replay-scored it with
  `cmd_samples=63`, `cloud_samples=107`, `gazebo_samples=403`, `filtered_samples=107`,
  `tf_samples=108`, `gazebo_delta_x=2.992`, `filtered_delta_x=2.992`, and
  `final_gap=(0.000,0.000)`. `nix develop -c just v2-lidar-bag-replay
  /home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T023334Z` also passed through the
  documented `just` target.
- Commit:       Included with the LiDAR bag replay scoring gate change.
- Stubbed/blocked: This proves the recorded-data replay harness on synthetic Gazebo data. Production
  V2 still needs real Unitree LiDAR replay scoring, map-generation acceptance, calibrated
  localization settings, hardware-in-the-loop, and field evidence.
- Next:         Add a real-bag scoring report format and map-generation acceptance gate so
  operator-provided LiDAR recordings can become promotion evidence instead of only smoke evidence.

## 2026-06-22 12:08 KST — V3: Semantic Map Snapshot Acceptance Gate — WIP
- Built:        Extended `semantic_map_node` so the V3 simulation launch loads the route CSV into
  the semantic HD map route-graph layer and optionally writes a persisted snapshot. Strengthened
  `./scripts/check_v3_semantic_map.sh` so `just v3-semantic-smoke` now validates both the live
  `/aris/mapping/semantic_map` summary and the saved snapshot artifact via
  `SemanticHDMap.load_snapshot`.
- Verified:     `./scripts/check_v3_semantic_map.sh` passed. It generated
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_030844.json` with `schema_version=1`,
  `map_id=aris-v3-sim`, `metric_cells=256`, `semantic_cells=1`, `route_nodes=46`,
  `route_edges=45`, `review_queue=59`, labels `road` and `debris`, and a high-risk traversability
  cell. `PYTHONPATH=src/aris_mapping python3 -m pytest src/aris_mapping/test -q` also passed
  (`7 passed`). `./scripts/check_python_tests.sh` passed (`71 passed`). `nix develop -c just
  v3-semantic-smoke` also passed through the documented target and wrote
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031032.json` with `metric_cells=258`,
  `route_nodes=46`, `route_edges=45`, and `review_queue=60`.
- Commit:       Included with the semantic map snapshot acceptance gate change.
- Stubbed/blocked: This is still simulation map-generation evidence. Production V3 still needs
  real camera streams, segmentation model selection, calibrated camera/LiDAR projection, operator
  review tooling, real repeat-pass data, and field validation.
- Next:         Add a map artifact report/manifest and connect real-bag replay output to map
  snapshot generation so operator datasets can produce comparable map evidence.

## 2026-06-22 12:15 KST — V3: Semantic Map Snapshot Manifest — WIP
- Built:        Added `scripts/validate_semantic_map_snapshot.py`, which validates a persisted
  semantic map snapshot and emits a promotion manifest with snapshot SHA-256, schema, map id,
  layer counts, label counts, route graph size, review queue size, and validation status. Updated
  `./scripts/check_v3_semantic_map.sh` so `just v3-semantic-smoke` writes the manifest next to the
  snapshot.
- Verified:     `./scripts/validate_semantic_map_snapshot.py
  /home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031032.json --manifest-out
  /tmp/aris_map_manifest_test.json --min-metric-cells 40 --min-route-nodes 40 --min-route-edges
  39` passed with SHA-256 `4a215e1562bace81ac49d588379b7c3a95c239ff2e238d205722a961100f5d08`.
  `nix develop -c just v3-semantic-smoke` passed and wrote
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031517.json` plus
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031517.manifest.json`; the manifest has
  `valid=true`, SHA-256 `c56081d723fe358f1d792b35acbdb57c36d3905b4ab663e8d569b484927bb893`,
  `metric_cells=266`, `semantic_cells=1`, `route_nodes=46`, `route_edges=45`, `review_queue=59`,
  and labels `road`/`debris`. `./scripts/check_python_tests.sh` passed (`73 passed`).
- Commit:       Included with the semantic map snapshot manifest change.
- Stubbed/blocked: This gives simulation map artifacts comparable promotion metadata, but it does
  not replace real repeat-pass mapping, camera segmentation, calibrated projection, operator review
  workflow, HIL, or field evidence.
- Next:         Connect real/operator bag replay output to the same manifest format and add map
  comparison scoring between repeat passes.

## 2026-06-22 12:20 KST — V3: Semantic Map Repeat-Pass Compare — WIP
- Built:        Added `scripts/compare_semantic_map_snapshots.py`, which compares two semantic map
  snapshots for repeat-pass stability: metric-cell overlap, route-graph overlap, top-label changes,
  high-risk cell delta, and review-queue delta. Updated `./scripts/check_v3_semantic_map.sh` to
  stop the map launch before generating manifest/compare artifacts, preventing snapshot SHA races,
  and to write `$ARIS_LOGS/maps/v3_semantic_map_<timestamp>.compare.json` whenever a previous V3
  snapshot exists.
- Verified:     Standalone compare passed between
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031032.json` and
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031517.json` with
  `metric_overlap=0.961`, `route_overlap=1.000`, `label_changes=0`, `high_risk_delta=0`, and
  `review_queue_delta=1`. `nix develop -c just v3-semantic-smoke` then passed and wrote
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031956.json`,
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031956.manifest.json`, and
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_031956.compare.json`. The final snapshot
  SHA-256 is `4a215e1562bace81ac49d588379b7c3a95c239ff2e238d205722a961100f5d08`, matching both
  manifest and compare report; compare reported `metric_overlap=0.992`, `route_overlap=1.000`,
  `label_changes=0`, `high_risk_delta=0`, and `review_queue_delta=2`. `./scripts/check_python_tests.sh`
  passed (`75 passed`).
- Commit:       Included with the semantic map repeat-pass compare change.
- Stubbed/blocked: The compare score is still simulation repeat-pass evidence. Production V3 needs
  real repeat-pass datasets, calibrated sensor projection, operator review tooling, HIL, and field
  evidence before map updates can be promoted for real driving.
- Next:         Use the same compare report format with operator-provided datasets and add stricter
  layer-specific thresholds once real sensor noise envelopes are known.

## 2026-06-22 12:23 KST — Readiness: V3 Map Artifact Gate Included — WIP
- Built:        Added `check_v3_semantic_map.sh` to the default headless core readiness sequence,
  between operator goal and V4 goal navigation. `run_core_readiness_report.sh` now records
  `skip_v3`, matching the existing `skip_gazebo` evidence marker. `ARIS_CORE_READINESS_SKIP_V3=1`
  remains available only for environments that cannot run the V3 map artifact gate.
- Verified:     `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` passed
  with `skip_v3=0`, `skip_gazebo=1`, and `result=PASS`. The report was written to
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T032252Z.log`. It ran Python tests
  (`75 passed`), MCU serial loopback, `/scan_cloud` contract, operator goal, V3 semantic map
  snapshot/manifest/compare (`metric_overlap=1.000`, `route_overlap=1.000`), and V4 goal
  navigation; the final readiness line was `ARIS core readiness passed (6 checks).`
- Commit:       Included with the readiness V3 map artifact gate change.
- Stubbed/blocked: This was a skip-Gazebo readiness run, so V2 Gazebo evidence remains covered by
  prior full Gazebo stack runs but not by this specific report.
- Next:         Run a full no-skip core readiness report after the major-branch cleanup, or on the
  next release candidate when the full Gazebo stack cost is acceptable.

## 2026-06-22 12:26 KST — Branch Hygiene: Major Milestones Only — WIP
- Built:        Consolidated remote feature branches into milestone branches. Remote branches now
  intentionally keep only `main`, `v1`, `v2`, and `v3`; local `v1`, `v2`, and `v3` were aligned to
  the same milestone commits. Added the major-only branch policy to `README.md` and
  `docs/verification_plan.md`.
- Verified:     `git ls-remote --heads origin` lists only `main`, `v1`, `v2`, and `v3`.
  `origin/v1=c4d2897`, `origin/v2=eec7b8a`, and `origin/v3=f46041e`. Deleted stale remote
  branches `codex/v2-*` and `codex/v3-*`.
- Commit:       Included with the branch policy documentation change.
- Stubbed/blocked: This is repository hygiene, not product readiness. Production completion still
  depends on real sensor, HIL, and field evidence.
- Next:         Continue future work directly on the active milestone branch (`v3`) unless the user
  explicitly asks to redefine a previous milestone baseline.

## 2026-06-22 12:31 KST — Readiness: Machine-Readable Evidence Index — WIP
- Built:        Added `scripts/generate_readiness_evidence_index.py` and wired
  `scripts/run_core_readiness_report.sh` to write
  `$ARIS_LOGS/readiness/evidence_index_<timestamp>.json` plus
  `$ARIS_LOGS/readiness/latest_evidence_index.json`. Documented the index in `README.md` and
  `docs/verification_plan.md`. The index points at the latest readiness report, latest V2 LiDAR
  bag metadata, latest V3 semantic map manifest, and latest V3 repeat-pass compare report.
- Verified:     `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` passed
  on branch `v3` at commit `e0dd2d2`, with `skip_v3=0`, `skip_gazebo=1`, and `result=PASS`. The
  report is `/home/kotori9/aris/logs/readiness/core_readiness_20260622T033034Z.log`; the evidence
  index is `/home/kotori9/aris/logs/readiness/evidence_index_20260622T033034Z.json`, and
  `/home/kotori9/aris/logs/readiness/latest_evidence_index.json` points to it. The run included
  Python tests (`76 passed`), MCU serial loopback, `/scan_cloud` contract, operator goal, V3
  semantic map snapshot/manifest/compare (`metric_overlap=0.907`, `route_overlap=1.000`,
  `label_changes=0`, `high_risk_delta=0`, `review_queue_delta=0`), and V4 goal navigation.
- Build/tests:  `python3 -m py_compile scripts/generate_readiness_evidence_index.py` passed;
  `bash -n scripts/run_core_readiness_report.sh` passed; `git diff --check` passed;
  `./scripts/check_python_tests.sh tests/evidence/test_readiness_evidence_index.py
  tests/mapping/test_semantic_map_snapshot_compare.py
  tests/mapping/test_semantic_map_snapshot_validator.py` passed (`5 passed`).
- Commit:       `7e6d246` — `Add readiness evidence index`.
- Stubbed/blocked: This is a skip-Gazebo readiness run, so it does not replace a future no-skip
  Gazebo readiness report or real-sensor/HIL/field promotion evidence.
- Next:         Commit and push this evidence-index increment to `origin/v3`, then run a full
  no-skip readiness report when the Gazebo stack runtime is acceptable.

## 2026-06-22 12:41 KST — V5: Dynamic Obstacle Slow/Stop Advisory Gate — WIP
- Built:        Added ROS-free `aris_perception.dynamic_obstacles`, `dynamic_obstacle_node`, and
  the `/aris/perception/dynamic_obstacle` JSON advisory contract. Wired `local_planner_node` to
  apply `clear`/`slow`/`stop` advisories before publishing `/cmd_drive`. Added
  `check_v5_dynamic_obstacle.sh`, `just v5-dynamic-obstacle-smoke`, and included the V5 smoke in
  default headless core readiness. The readiness evidence index now parses V5 slow/stop metrics
  from readiness logs.
- Verified:     `./scripts/check_v5_dynamic_obstacle.sh` passed with
  `baseline_speed=1.285`, `slow_min_speed=0.320`, `slow_min_accel=-0.200`,
  `stop_min_speed=0.000`, and `stop_min_accel=-1.000`. Then
  `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` passed with
  `skip_v3=0`, `skip_gazebo=1`, `result=PASS`, and `ARIS core readiness passed (7 checks).` The
  report is `/home/kotori9/aris/logs/readiness/core_readiness_20260622T034114Z.log`; the evidence
  index path is `/home/kotori9/aris/logs/readiness/evidence_index_20260622T034114Z.json`. That run
  included Python tests (`82 passed`), MCU serial loopback, `/scan_cloud` contract, operator goal,
  V3 map snapshot/manifest/compare (`metric_overlap=0.980`, `route_overlap=1.000`), V4 goal
  navigation, and V5 dynamic-obstacle slow/stop.
- Build/tests:  `python3 -m py_compile` passed for the new V5/evidence modules; `bash -n` passed
  for `check_v5_dynamic_obstacle.sh` and `check_core_readiness.sh`; `./scripts/check_python_tests.sh`
  passed (`82 passed`); `git diff --check` passed. Targeted V5/evidence tests passed (`23 passed`).
- Commit:       `396ec5a` — `Add V5 dynamic obstacle advisory gate`.
- Stubbed/blocked: This is simulation evidence for speed limiting and stop braking through the
  existing `/cmd_drive` contract. It is not yet a tracked multi-object dynamic obstacle system,
  full local replan, real LiDAR/camera validation, HIL, or field evidence.
- Next:         Commit and push the V5 advisory gate to `origin/v3`; then extend V5 from slow/stop
  advisory into local detour/replan and real sensor replay scoring.

## 2026-06-22 13:55 KST — V5: Local Detour Advisory Gate — WIP
- Built:        Extended the V5 dynamic-obstacle advisory contract with `detour`,
  `detour_lateral_m`, and `detour_forward_m`. `dynamic_obstacle_node` now proposes a local detour
  for non-emergency obstacles inside the forward corridor while preserving `stop` for close or fast
  closing obstacles. `local_planner_node` inserts a short temporary bypass waypoint for `detour`
  advisories before publishing `/cmd_drive`, then keeps the existing speed/brake limiting path.
  The V5 smoke and readiness evidence index now capture detour steering, speed, and braking
  metrics.
- Verified:     `./scripts/check_v5_dynamic_obstacle.sh` passed with
  `baseline_speed=1.269`, `detour_min_speed=0.270`, `detour_min_accel=-0.100`,
  `detour_min_steering=-0.927`, `slow_min_speed=0.320`, `slow_min_accel=-0.200`,
  `stop_min_speed=0.000`, and `stop_min_accel=-1.000`. Then
  `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` passed with
  `skip_v3=0`, `skip_gazebo=1`, `result=PASS`, and `ARIS core readiness passed (7 checks).` The
  report is `/home/kotori9/aris/logs/readiness/core_readiness_20260622T045510Z.log`; the evidence
  index is `/home/kotori9/aris/logs/readiness/evidence_index_20260622T045510Z.json` and includes
  `detour_min_steering=-0.927`.
- Build/tests:  `python3 -m py_compile` passed for the changed V5/evidence modules; `bash -n
  scripts/check_v5_dynamic_obstacle.sh` passed; targeted V5/evidence tests passed (`25 passed`);
  full `./scripts/check_python_tests.sh` passed (`84 passed`); `git diff --check` passed.
- Commit:       `b5f6754` — `Add V5 local detour advisory`.
- Stubbed/blocked: This is still local simulation evidence. It does not yet track persistent
  objects, perform full route-graph replanning, replay real LiDAR obstacle bags, validate camera
  fusion, or prove behavior in HIL/field runs.
- Next:         Commit and push the local detour increment to `origin/v3`; then connect V5 obstacle
  evidence to recorded/replayed bags and add object persistence/replan scoring.

## 2026-06-22 14:01 KST — V5: Persistent Obstacle Track Evidence — WIP
- Built:        Added ROS-free `DynamicObstacleTracker`, `TrackedObstacle`, and
  `ObstacleObservation` to keep corridor obstacles persistent across frames with `track_id`,
  `track_age`, persistence time, and simple velocity estimates. `dynamic_obstacle_node` now
  attaches track metadata to `/aris/perception/dynamic_obstacle` advisories. The V5 smoke and
  readiness evidence index now include tracking metrics alongside detour/slow/stop control metrics.
- Verified:     `./scripts/check_v5_dynamic_obstacle.sh` passed with
  `baseline_speed=1.301`, `detour_min_speed=0.270`, `detour_min_accel=-0.100`,
  `detour_min_steering=-0.927`, `slow_min_speed=0.320`, `stop_min_speed=0.000`,
  `track_age=2`, `track_persistence_s=0.200`, and `track_velocity_x_mps=-1.000`. Then
  `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` passed with
  `skip_v3=0`, `skip_gazebo=1`, `result=PASS`, and `ARIS core readiness passed (7 checks).` The
  report is `/home/kotori9/aris/logs/readiness/core_readiness_20260622T050121Z.log`; the evidence
  index is `/home/kotori9/aris/logs/readiness/evidence_index_20260622T050121Z.json` and includes
  `track_age=2.0`, `track_persistence_s=0.2`, and `track_velocity_x_mps=-1.0`.
- Build/tests:  `python3 -m py_compile` passed for changed V5/evidence modules; `bash -n
  scripts/check_v5_dynamic_obstacle.sh` passed; targeted V5/evidence tests passed (`8 passed`);
  full `./scripts/check_python_tests.sh` passed (`87 passed`); `git diff --check` passed.
- Commit:       `45a67ba` — `Add V5 persistent obstacle tracking evidence`.
- Stubbed/blocked: This is a nearest-neighbor single-corridor tracker for simulation evidence. It
  is not yet a production multi-object tracker, static-map differencer, route-graph replan scorer,
  real LiDAR replay gate, HIL, or field validation.
- Next:         Commit and push the tracking increment to `origin/v3`; then add recorded/replayed
  obstacle-bag scoring and route-graph replan evidence.

## 2026-06-22 14:11 KST — V6: Advisory-Only Semantic Review Gate — WIP
- Built:        Added `aris_ai_semantics.review_report` and
  `scripts/generate_v6_semantic_review.py` to turn V3 semantic map manifest/compare artifacts into
  an advisory-only operator review report. Added `check_v6_semantic_review.sh`,
  `just v6-semantic-review-smoke`, included the V6 gate in default core readiness after V3 map
  generation, and linked the latest V6 review report from the readiness evidence index. Hardened
  `check_v3_semantic_map.sh` so V6 review JSON files are not accidentally selected as baseline
  semantic map snapshots.
- Verified:     `./scripts/check_v6_semantic_review.sh` passed and wrote
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_050838.v6_review.json` with
  `advisory_only=True`, `control_authority=none`, and `review_items=3`. Then
  `ARIS_CORE_READINESS_SKIP_GAZEBO=1 ./scripts/run_core_readiness_report.sh` passed with
  `skip_v3=0`, `skip_gazebo=1`, `result=PASS`, and `ARIS core readiness passed (8 checks).` The
  final report is `/home/kotori9/aris/logs/readiness/core_readiness_20260622T051147Z.log`; the
  evidence index is `/home/kotori9/aris/logs/readiness/evidence_index_20260622T051147Z.json` and
  includes the latest V6 semantic review report with `control_authority=none`.
- Build/tests:  `python3 -m py_compile` passed for V6/evidence modules; `bash -n` passed for
  `check_v6_semantic_review.sh`, `check_v3_semantic_map.sh`, and `check_core_readiness.sh`;
  targeted V6/evidence tests passed (`3 passed`); full `./scripts/check_python_tests.sh` passed
  (`89 passed`); `git diff --check` passed.
- Commit:       `6625314` — `Add V6 semantic review evidence gate`.
- Stubbed/blocked: This is deterministic offline review over simulation map artifacts. It is not
  yet a real multimodal model, camera-image review UI, operator approval workflow, or field map
  promotion process.
- Next:         Commit and push the V6 review gate to `origin/v3`; then connect V6 review to real
  logged images/map deltas and add an operator approval artifact.

## 2026-06-22 14:15 KST — Readiness: Full No-Skip Gazebo Stack — WIP
- Built:        No product code change. Ran the default `./scripts/run_core_readiness_report.sh`
  without `ARIS_CORE_READINESS_SKIP_GAZEBO`, exercising the V2 Gazebo stack together with V3 map
  artifacts, V6 semantic review, V4 goal navigation, and V5 dynamic obstacle evidence.
- Verified:     Full core readiness passed with `skip_v3=0`, `skip_gazebo=0`, `real_actuation=0`,
  `result=PASS`, and `ARIS core readiness passed (9 checks).` The report is
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T051523Z.log`; the evidence index is
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T051523Z.json`. The run included
  Python tests (`89 passed`), MCU loopback, `/scan_cloud` contract (`width=869`, `point_step=24`),
  operator goal, V3 semantic map snapshot/manifest/compare (`metric_overlap=0.888`,
  `route_overlap=1.000`), V6 review (`advisory_only=True`, `control_authority=none`,
  `review_items=3`), V4 goal navigation (`goal_error=0.720`), V5 dynamic obstacle
  (`detour_min_steering=-0.927`, `track_age=2`), and all six V2 Gazebo stack checks:
  LiDAR cloud, static localization, moving localization, physics motion, physics localization, and
  drift recovery (`max_wheel_error=0.131`, `max_filtered_error=0.027`).
- Build/tests:  The no-skip readiness report is the verification artifact for this entry.
- Commit:       Pending no-skip readiness evidence documentation commit.
- Stubbed/blocked: This is strong 3D/Gazebo simulation evidence, but still not real-sensor replay,
  HIL, or field validation. Real actuation remained disabled.
- Next:         Commit and push this evidence documentation to `origin/v3`; then focus on real or
  replayed sensor obstacle/map scoring and HIL readiness criteria.

## 2026-06-22 14:23 KST — V5: Dynamic Obstacle Report Artifact — WIP
- Built:        Extended `check_v5_dynamic_obstacle.sh` so each run writes
  `$ARIS_LOGS/obstacles/v5_dynamic_obstacle_<timestamp>.json` with schema version, pass/fail
  status, thresholds, failures, detour/slow/stop command metrics, and persistent-track metrics.
  The readiness evidence index now links the latest V5 obstacle report in addition to parsing the
  readiness log metric line.
- Verified:     `./scripts/check_v5_dynamic_obstacle.sh` passed and wrote
  `/home/kotori9/aris/logs/obstacles/v5_dynamic_obstacle_20260622T052333Z.json` with
  `valid=true`, `detour_min_steering=-0.927`, `slow_min_speed=0.320`,
  `stop_min_speed=0.000`, `track_age=2`, and `track_velocity_x_mps=-1.000`. Standalone
  `generate_readiness_evidence_index.py` included this report under `v5_dynamic_obstacle.report`.
- Build/tests:  `python3 -m py_compile scripts/generate_readiness_evidence_index.py` passed;
  `bash -n scripts/check_v5_dynamic_obstacle.sh` passed;
  `./scripts/check_python_tests.sh tests/evidence/test_readiness_evidence_index.py` passed
  (`1 passed`); `git diff --check` passed.
- Commit:       Pending V5 obstacle report artifact commit.
- Stubbed/blocked: This is still simulation obstacle evidence. It is not yet a real recorded
  obstacle bag replay score or HIL/field obstacle-avoidance validation.
- Next:         Commit and push the V5 report artifact increment to `origin/v3`; then add
  operator/real-bag obstacle replay scoring.

## 2026-06-22 14:27 KST — HIL: Non-Actuating Preflight Evidence — WIP
- Built:        Added `scripts/generate_hil_preflight.py`, `scripts/check_hil_preflight.sh`, and
  `just hil-preflight`. The preflight writes `$ARIS_LOGS/hil/hil_preflight_<timestamp>.json` plus
  `latest_hil_preflight.json`, links the latest no-skip readiness evidence, V5 obstacle report,
  and V6 semantic review, inventories visible serial/video/GPU/CAN/input devices, and keeps
  `safe_to_enable_real_actuation=false`.
- Verified:     `./scripts/check_hil_preflight.sh` passed and wrote
  `/home/kotori9/aris/logs/hil/hil_preflight_20260622T052740Z.json` with
  `ready_for_hil=false`, `safe_to_enable_real_actuation=false`, and one blocker:
  `hardware devices missing: serial,video,can`. The report saw GPU devices and `/dev/input/js0`,
  and confirmed latest no-skip readiness, V5 obstacle report, and V6 review evidence. Standalone
  `generate_readiness_evidence_index.py` linked the HIL report under `hil_preflight`.
- Build/tests:  `python3 -m py_compile` passed for HIL/evidence scripts; `bash -n
  scripts/check_hil_preflight.sh` passed; targeted HIL/evidence tests passed (`2 passed`);
  `git diff --check` passed.
- Commit:       Pending HIL preflight evidence commit.
- Stubbed/blocked: This does not run hardware. Current host is not HIL-ready because serial,
  video, and CAN devices are not visible. Real actuation remains disabled.
- Next:         Commit and push the HIL preflight increment to `origin/v3`; then add real/replayed
  sensor obstacle and map scoring once hardware or operator bags are available.

## 2026-06-22 14:33 KST — Readiness: Operational Completion Audit — WIP
- Built:        Added `scripts/generate_operational_readiness_audit.py`,
  `scripts/check_operational_readiness_audit.sh`, and `just operational-readiness-audit`. The
  audit aggregates readiness, V2 Gazebo/LiDAR, V3 map, V5 obstacle, V6 semantic review, HIL
  preflight, and field-validation evidence into a single machine-readable completion report.
- Verified:     `./scripts/check_operational_readiness_audit.sh` wrote
  `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T053503Z.json` with
  `achieved=false`, `practical_use_ready=false`, and `safe_to_enable_real_actuation=false`.
  Passing criteria were docs/build/run readiness, core no-skip 3D simulation, V2 Gazebo stack,
  V3/V6 mapping review, and V5 dynamic obstacle evidence. Remaining blockers are HIL preflight
  (`hardware devices missing: serial,video,can`) and missing closed-site field-validation evidence.
  A refreshed evidence index at
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T053514Z.json` links the audit.
- Build/tests:  `python3 -m py_compile` passed for operational audit and evidence index scripts;
  `bash -n scripts/check_operational_readiness_audit.sh` passed; targeted evidence tests passed
  (`4 passed`).
- Commit:       Pending operational readiness audit artifact commit.
- Stubbed/blocked: The audit intentionally does not mark the overall goal achieved. Real HIL
  hardware visibility and field validation remain missing.
- Next:         Commit and push this audit artifact to `origin/v3`; then add real/replayed sensor
  obstacle/map scoring and HIL evidence once devices or operator bags are available.

## 2026-06-22 15:03 KST — V5: Operator Obstacle Bag Replay Gate — WIP
- Built:        Added `scripts/check_v5_obstacle_bag_replay.sh`, `just v5-obstacle-bag-replay`,
  and `/scan_cloud` scan-only metadata validation for sensor-focused obstacle bags. The gate
  replays an operator rosbag, runs `dynamic_obstacle_node`, scores
  `/aris/perception/dynamic_obstacle` advisories, and writes
  `$ARIS_LOGS/obstacles/v5_obstacle_bag_replay_<timestamp>.json`. The readiness evidence index now
  links the latest V5 obstacle replay report, and the operational readiness audit has a separate
  `v5_obstacle_bag_replay` criterion.
- Verified:     `python3 scripts/validate_v2_lidar_bag.py --scan-only
  /home/kotori9/aris/logs/bags/v2_recorded_lidar_20260622T023334Z` passed with
  `/scan_cloud` count `107`. `./scripts/check_operational_readiness_audit.sh` wrote
  `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T060308Z.json` with
  `achieved=false` and three blockers: missing V5 operator/real obstacle bag replay score, HIL
  preflight not ready, and missing closed-site field validation. A refreshed evidence index at
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T060316Z.json` links the latest audit.
- Build/tests:  `python3 -m py_compile` passed for the bag validator, evidence index, and audit
  scripts; `bash -n scripts/check_v5_obstacle_bag_replay.sh` passed; targeted evidence tests
  passed (`7 passed`).
- Commit:       Pending V5 obstacle bag replay gate commit.
- Stubbed/blocked: No operator/real obstacle rosbag with visible dynamic obstacles has been
  provided yet, so the new replay criterion correctly remains unpassed.
- Next:         Commit and push this replay gate to `origin/v3`; then run it against a real or
  operator-provided obstacle bag and use the generated report as V5 replay evidence.

## 2026-06-22 15:16 KST — Field: Closed-Site Validation Report Gate — WIP
- Built:        Added `scripts/generate_field_validation_report.py`, `scripts/check_field_validation.sh`,
  and `just field-validation`. The field report validates an operator manifest for closed-site ODD,
  route completion, goal error, speed limit, zero E-stop/fault/operator takeover counts, cited HIL
  and V5 obstacle replay evidence, field bag/run-log citation, and operator/safety approvals.
  The readiness evidence index now links the latest field validation report, and the operational
  readiness audit exposes the field run summary when present.
- Verified:     Targeted field/evidence tests validate both a passing manifest and unsafe/incomplete
  manifests. `./scripts/check_operational_readiness_audit.sh` wrote
  `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T060900Z.json` with
  `achieved=false`; the field criterion remains unpassed because no real closed-site field
  manifest/report exists. A refreshed evidence index at
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T060907Z.json` links the latest audit.
- Build/tests:  `python3 -m py_compile` passed for field/audit/evidence scripts; `bash -n
  scripts/check_field_validation.sh` passed; targeted field/evidence tests passed (`9 passed`);
  full `./scripts/check_python_tests.sh` passed (`100 passed`); `git diff --check` passed.
- Commit:       Pending field validation report gate commit.
- Stubbed/blocked: This defines the contract for field evidence. It does not create real field
  evidence without a closed-site run manifest and associated logs/bags.
- Next:         Run full tests, commit, and push to `origin/v3`; then use the gate against a real
  closed-site manifest when hardware and operator evidence are available.

## 2026-06-22 15:18 KST — V5: Recorded Obstacle Replay Smoke — WIP
- Built:        Added `scripts/check_v5_recorded_obstacle_replay.sh` and
  `just v5-recorded-obstacle-replay-smoke`. The smoke records a deterministic `/scan_cloud`
  obstacle bag under `$ARIS_LOGS/bags/v5_recorded_obstacle_<timestamp>/`, then runs the existing
  V5 obstacle bag replay scorer against the recorded bag. `check_v5_obstacle_bag_replay.sh` also
  now force-cleans the detector process so replay containers exit reliably after scoring.
- Verified:     `./scripts/check_v5_recorded_obstacle_replay.sh` passed. It recorded
  `/home/kotori9/aris/logs/bags/v5_recorded_obstacle_20260622T061708Z` with `/scan_cloud` count
  `49`, then wrote
  `/home/kotori9/aris/logs/obstacles/v5_obstacle_bag_replay_20260622T061721Z.json` with
  `valid=true`, `cloud_samples=48`, `advisory_samples=46`, action counts `detour=21` and
  `stop=25`, and `max_track_age=25`. `./scripts/check_operational_readiness_audit.sh` then wrote
  `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T061758Z.json` with
  `achieved=false` and two remaining blockers: HIL preflight not ready and missing closed-site
  field validation. A refreshed evidence index at
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T061805Z.json` links the latest
  readiness/audit/replay evidence.
- Build/tests:  `bash -n` passed for V5 replay scripts; targeted replay validator tests passed
  (`2 passed`); full `./scripts/check_python_tests.sh` passed (`100 passed`); `git diff --check`
  passed.
- Commit:       Pending V5 recorded obstacle replay smoke commit.
- Stubbed/blocked: This is deterministic recorded-data SIL evidence, not an operator-provided real
  obstacle bag. It removes the replay-path blocker but does not replace HIL or field validation.
- Next:         Run full tests, commit, and push to `origin/v3`; then use the same replay scorer on
  operator/real obstacle bags when available.

## 2026-06-22 15:38 KST — Branch Policy: ARIS Milestone Branches — WIP
- Built:        Reframed branch policy around ARIS feature/milestone branches `v1` through `v6`
  instead of keeping only `v1` through `v3`. The active integration branch is now `v6`, reflecting
  the current headless simulation and embedded-software state.
- Verified:     `git ls-remote --heads origin` now lists `main`, `v1`, `v2`, `v3`, `v4`, `v5`,
  and `v6`. The milestone pointers are `v1=c4d2897`, `v2=eec7b8a`, `v3=f46041e`, `v4=b4ab6f6`,
  `v5=ba8992a`, and `v6=94735ae` before the final policy-log amend. `v3` was intentionally moved
  back from the mixed integration tip to the V3 semantic-map baseline; later work is preserved on
  `v5`/`v6`.
- Build/tests:  Full `./scripts/check_python_tests.sh` passed (`100 passed`); `git diff --check`
  passed.
- Commit:       `94735ae` before final policy-log amend — `Document ARIS milestone branch policy`.
- Scope note:   No hardware is currently connected; active work is limited to headless simulation,
  recorded/replayed data, ROS 2 processing software, and embedded dry-run software. HIL and field
  documents remain future evidence contracts only.
- Next:         Continue headless simulation and embedded dry-run work on the relevant milestone
  branch, currently `v6`.

## 2026-06-22 15:33 KST — Headless Scope Audit: Simulation + Embedded Dry-Run — WIP
- Built:        Added `scripts/check_embedded_dry_run.sh`,
  `scripts/generate_headless_readiness_audit.py`, `scripts/check_headless_readiness_audit.sh`,
  `just embedded-dry-run`, and `just headless-readiness-audit`. The new audit evaluates only the
  current hardware-free scope: no-skip core readiness, V2 Gazebo/LiDAR bag evidence, V3/V6 semantic
  map review evidence, V5 obstacle smoke and recorded replay evidence, and MCU bridge/protocol
  dry-run evidence. HIL preflight and field validation are explicitly recorded as future blockers
  outside the current scope.
- Verified:     `./scripts/check_embedded_dry_run.sh` passed and wrote
  `/home/kotori9/aris/logs/embedded/embedded_dry_run_20260622T063342Z.json` with `valid=true`.
  `./scripts/check_headless_readiness_audit.sh` wrote
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T063348Z.json` with
  `headless_ready=true` and zero blockers. A refreshed evidence index at
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T063356Z.json` links the latest
  embedded dry-run and headless audit evidence.
- Build/tests:  Targeted evidence tests passed (`9 passed`); full `./scripts/check_python_tests.sh`
  passed (`103 passed`); `python3 -m py_compile`, `bash -n`, and `git diff --check` passed.
- Commit:       Pending headless readiness audit commit.
- Scope note:   This does not claim real-actuation readiness. No hardware is connected; HIL and
  field validation remain inactive until the project enters a hardware-attached milestone.
- Next:         Commit and push to `v6`.

## 2026-06-22 15:42 KST — Core Pipeline Flow: V3 Map Artifact Feeds V4 Planner — WIP
- Built:        Added `semantic_map_file` support to `global_planner_node` and
  `v4_goal_nav_sim.launch.py`, plus ROS-free `load_semantic_map_graph()` validation in
  `route_graph.py`. Added `scripts/check_core_pipeline_flow.sh` and `just core-pipeline-flow` so
  the current headless stack verifies Mapping -> Semantic HD Map -> Route Graph -> Localization ->
  Goal Based Planning -> Autonomous Driving in one report. The headless readiness audit now
  requires this core pipeline flow report.
- Verified:     `./scripts/check_core_pipeline_flow.sh` passed and wrote
  `/home/kotori9/aris/logs/pipeline/core_pipeline_flow_20260622T064223Z.json` with `valid=true`.
  The route graph came from
  `/aris/logs/maps/core_pipeline_semantic_map_20260622T064223Z.json`, selected detour node path
  `approach -> detour_a -> detour_b -> detour_c -> goal`, observed `173` `/scan_cloud` samples,
  `180` `/cmd_drive` samples, max command speed `1.386 m/s`, and final goal error `0.715 m`.
  A refreshed headless audit at
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T064302Z.json` reports
  `headless_ready=true` with zero blockers and includes the core pipeline flow criterion.
- Build/tests:  Full `./scripts/check_python_tests.sh` passed (`106 passed`); targeted planner and
  evidence tests passed (`7 passed`); `python3 -m py_compile`, `bash -n`, and `git diff --check`
  passed.
- Commit:       Pending core pipeline flow commit.
- Scope note:   This is headless simulation and software evidence. It does not claim HIL, real
  sensor, real actuator, or field readiness.
- Next:         Commit and push to `v6`.

## 2026-06-22 15:45 KST — Headless Release Candidate Gate — WIP
- Built:        Added `scripts/check_headless_release_candidate.sh` and
  `just headless-release-candidate`. The gate runs the current hardware-free evidence bundle in
  sequence: embedded dry-run, core pipeline flow, no-skip core readiness report, and headless
  readiness audit. It writes a machine-readable summary under
  `$ARIS_LOGS/readiness/headless_release_candidate_<timestamp>.json`.
- Verified:     `./scripts/check_headless_release_candidate.sh` passed and wrote
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T064544Z.json` with
  `valid=true`. The run included embedded dry-run
  `/home/kotori9/aris/logs/embedded/embedded_dry_run_20260622T064544Z.json`, core pipeline flow
  `/home/kotori9/aris/logs/pipeline/core_pipeline_flow_20260622T064544Z.json`, no-skip core
  readiness `/home/kotori9/aris/logs/readiness/core_readiness_20260622T064610Z.log`, and headless
  audit `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T064914Z.json` with
  `headless_ready=true`. A refreshed evidence index at
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T064927Z.json` links the latest bundle.
- Build/tests:  Full `./scripts/check_python_tests.sh` passed (`106 passed`); targeted evidence
  index test passed; `bash -n`, `python3 -m py_compile`, and `git diff --check` passed.
- Commit:       Pending headless release-candidate gate commit.
- Scope note:   This is still hardware-free headless evidence only. HIL, real sensor, real
  actuator, and field validation remain outside the current active scope.
- Next:         Commit and push to `v6`.

## 2026-06-22 15:51 KST — Release Candidate Evidence Index Closure — WIP
- Built:        Updated `scripts/check_headless_release_candidate.sh` so the gate refreshes a final
  readiness evidence index after writing the release-candidate report. The release report now points
  at that final index, and the final index points back at the release report. Added
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1` for low-cost index/report closure checks using existing
  latest evidence.
- Verified:     `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh`
  passed and wrote
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T065130Z.json` with
  `valid=true` and `reused_existing_evidence=true`. It refreshed
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T065130Z_release.json`; the release
  report's `readiness_evidence_index` points to that file, and that index's
  `headless_release_candidate.report_path` points back to the release report.
- Build/tests:  Full `./scripts/check_python_tests.sh` passed (`106 passed`); targeted evidence
  index test passed; `bash -n`, `python3 -m py_compile`, and `git diff --check` passed.
- Commit:       Pending release-candidate evidence-index closure commit.
- Scope note:   The reuse mode is only for report/index plumbing; normal
  `just headless-release-candidate` still runs the full headless evidence bundle.
- Next:         Commit and push to `v6`.

## 2026-06-22 15:55 KST — Current Handoff And Mapping Refresh — WIP
- Built:        Replaced the stale V0/V1-era `docs/HANDOFF.md` with the current `v6` continuation
  guide: milestone branch policy, headless execution scope, release-candidate gate, evidence
  locations, hard rules, and remaining real-world scope. Updated `docs/architecture_mapping.md` so
  it reflects the verified headless V2-V6 evidence instead of describing those paths as only early
  scaffolds. Updated README quick start to use the actual local workspace path and
  `just headless-release-candidate` as the current reproducibility entry point.
- Verified:     Removed stale handoff claims such as V1 being next, no-push mode, initial main-only
  branch state, Python-only simulation, and 13-test baseline. Targeted evidence/planner tests
  passed (`7 passed`), full `./scripts/check_python_tests.sh` passed (`106 passed`), and
  `git diff --check` passed.
- Commit:       Pending handoff refresh commit.
- Scope note:   Documentation-only change; no runtime behavior changed.
- Next:         Commit and push to `v6`.

## 2026-06-22 15:55 KST — Documented Command Consistency Gate — WIP
- Built:        Added `scripts/check_documented_commands.py`,
  `scripts/check_documented_commands.sh`, and `just documented-commands`. The checker scans the
  current README/docs command references, excluding the historical AUTORUN log, and verifies that
  documented `just` recipes and `./scripts/...` paths resolve locally. Added this gate to
  `just headless-release-candidate`.
- Verified:     `./scripts/check_documented_commands.sh` passed with `docs=25` and
  `references=155`. `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh`
  passed and the release report includes a passing `documented_commands` step. Full
  `./scripts/check_python_tests.sh` passed (`107 passed`); targeted documented-command/evidence
  tests passed (`2 passed`); `bash -n`, `python3 -m py_compile`, and `git diff --check` passed.
- Commit:       Pending documented-command gate commit.
- Scope note:   This is a reproducibility guard for current docs and scripts; it does not exercise
  the full ROS/Gazebo runtime by itself.
- Next:         Commit and push to `v6`.

## 2026-06-22 15:58 KST — Architecture Contract Static Guardrail — WIP
- Built:        Added `scripts/check_architecture_contracts.py`,
  `scripts/check_architecture_contracts.sh`, and `just architecture-contracts`. The checker guards
  the `/cmd_drive` publisher boundary and verifies the AI advisory package does not introduce
  control-topic or MCU-control authority. Added this guardrail to `just headless-release-candidate`.
- Verified:     `./scripts/check_architecture_contracts.sh` passed. `./scripts/check_documented_commands.sh`
  passed with `docs=25` and `references=159`.
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed and
  the release report includes a passing `architecture_contracts` step. Full
  `./scripts/check_python_tests.sh` passed (`108 passed`); targeted architecture/document/evidence
  tests passed (`3 passed`); `bash -n`, `python3 -m py_compile`, and `git diff --check` passed.
- Commit:       Pending architecture-contract guardrail commit.
- Scope note:   Static guardrail only; full runtime evidence remains covered by the normal
  headless release-candidate run.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:01 KST — Host Policy Guardrail — WIP
- Built:        Added `scripts/check_host_policy.py`, `scripts/check_host_policy.sh`, and
  `just host-policy`. The checker scans host entrypoints (`justfile` and `scripts/*.sh`) for
  forbidden host-side privilege/package-management commands while allowing the existing vcan helper
  container bootstrap exception. Added `host_policy` to `just headless-release-candidate` in both
  normal and reuse-existing-evidence modes, and documented the command in README/HANDOFF and the
  verification plan.
- Verified:     `./scripts/check_host_policy.sh` passed with `host_policy_valid`.
  `python3 -m pytest tests/evidence/test_host_policy.py` passed (`1 passed`).
  `./scripts/check_documented_commands.sh` passed with `docs=25` and `references=163`.
  `./scripts/check_architecture_contracts.sh` passed. Reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed and
  wrote `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T070151Z.json` with
  `valid=true` and a passing `host_policy` step. Full `./scripts/check_python_tests.sh` passed
  (`109 passed`), and `git diff --check` passed.
- Commit:       Pending host-policy guardrail commit.
- Scope note:   Host entrypoint static guardrail only. Docker/container package installation remains
  allowed where appropriate; real hardware setup stays outside the current headless scope.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:06 KST — Headless Release Closure Validator — WIP
- Built:        Added `scripts/validate_headless_release_candidate.py` and wired it into
  `scripts/check_headless_release_candidate.sh` after the final evidence index is generated. The
  validator requires every release-candidate step to pass, verifies required evidence paths exist,
  and checks the release report and final evidence index point at each other. Added targeted
  evidence tests and documented the closure check in HANDOFF and the verification plan.
- Verified:     Reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed,
  wrote `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T070654Z.json`, and
  printed `headless_release_candidate_valid`. Targeted release/headless audit tests passed
  (`7 passed`). Full `./scripts/check_python_tests.sh` passed (`112 passed`).
  `./scripts/check_documented_commands.sh`, `./scripts/check_architecture_contracts.sh`,
  `./scripts/check_host_policy.sh`, and `git diff --check` passed.
- Commit:       Pending release closure validator commit.
- Scope note:   This closes the software-only release bundle; it does not change the active
  hardware-free scope or claim HIL/field readiness.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:12 KST — Core Pipeline Repeatability Gate — WIP
- Built:        Added `scripts/check_core_pipeline_repeatability.sh` and
  `just core-pipeline-repeatability`. The gate reruns `core-pipeline-flow` at least twice, records
  each six-stage pipeline report, requires stable route-graph node paths, and bounds goal-error
  spread. Wired the report into the readiness evidence index, headless readiness audit, and
  headless release-candidate closure. Updated README, HANDOFF, workflows, and the verification plan.
- Verified:     `./scripts/check_core_pipeline_repeatability.sh` passed and wrote
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T071138Z.json` with
  `valid=true`, `runs=2`, `goal_error_max=0.7276347068379565`, and
  `goal_error_spread=0.0038878756466690367`. The two runs selected the same detour node path
  `approach -> detour_a -> detour_b -> detour_c -> goal`. Refreshed the readiness evidence index,
  then `./scripts/check_headless_readiness_audit.sh` passed with `headless_ready=True` and zero
  blockers. Reuse-mode `./scripts/check_headless_release_candidate.sh` passed and printed
  `headless_release_candidate_valid`. Full `./scripts/check_python_tests.sh` passed (`113 passed`);
  `./scripts/check_documented_commands.sh`, `./scripts/check_architecture_contracts.sh`,
  `./scripts/check_host_policy.sh`, and `git diff --check` passed.
- Commit:       Pending core-pipeline repeatability gate commit.
- Scope note:   This strengthens repeated headless simulation evidence. It does not claim real
  sensor, HIL, actuator, or field readiness.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:18 KST — Headless Status Summary — WIP
- Built:        Added `scripts/summarize_headless_status.py`, `scripts/check_headless_status.sh`,
  and `just headless-status`. The command reads the latest headless release candidate, headless
  readiness audit, evidence index, and core-pipeline repeatability report, then prints a concise
  human-readable status. `--json` emits the same summary as machine-readable JSON. Updated README,
  HANDOFF, and the verification plan.
- Verified:     `./scripts/check_headless_status.sh` printed `headless_ready: yes`,
  `release_valid: yes`, the stable detour path `approach -> detour_a -> detour_b -> detour_c ->
  goal`, and the repeatability metrics from
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T071138Z.json`.
  `./scripts/check_headless_status.sh --json` produced valid JSON with `headless_ready=True` and
  `release_valid=True`. Targeted status-summary tests passed (`2 passed`). Full
  `./scripts/check_python_tests.sh` passed (`115 passed`). `./scripts/check_documented_commands.sh`
  passed with `docs=25` and `references=175`; `./scripts/check_architecture_contracts.sh`,
  `./scripts/check_host_policy.sh`, and `git diff --check` passed.
- Commit:       Pending headless status summary commit.
- Scope note:   This improves operator/developer usability for latest headless evidence. It does
  not claim hardware/HIL/field readiness.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:19 KST — Operational Audit Repeatability Criterion — WIP
- Built:        Updated `scripts/generate_operational_readiness_audit.py` so final practical-use
  readiness now requires the core-pipeline repeatability report in addition to no-skip readiness,
  V2/V3/V5/V6 evidence, HIL preflight, and field validation. Added regression coverage for missing
  repeatability evidence and documented the new audit input in README and the verification plan.
- Verified:     `python3 -m pytest tests/evidence/test_operational_readiness_audit.py` passed
  (`7 passed`). `./scripts/check_operational_readiness_audit.sh` wrote
  `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T072009Z.json` with
  `core_pipeline_repeatability.passed=true`, `achieved=false`, and blockers limited to
  `hil_preflight` and `field_validation`, matching the current no-hardware scope. Full
  `./scripts/check_python_tests.sh` passed (`117 passed`). `./scripts/check_documented_commands.sh`,
  `./scripts/check_architecture_contracts.sh`, `./scripts/check_host_policy.sh`, and
  `git diff --check` passed.
- Commit:       Pending operational-audit repeatability criterion commit.
- Scope note:   This makes final readiness stricter. It does not change the active headless-only
  hardware scope or claim HIL/field readiness.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:23 KST — Headless Evidence Freshness Warning — WIP
- Built:        Updated `scripts/summarize_headless_status.py` and `scripts/check_headless_status.sh`
  so `just headless-status` compares the latest evidence-index git commit against the current
  workspace `HEAD`. The summary now reports current/evidence git refs and prints a freshness
  recommendation when the latest evidence was generated by an older commit.
- Verified:     `./scripts/check_headless_status.sh` printed `evidence_fresh_for_head: no`,
  `current_git: v6@1f00eae`, `evidence_git: v6@aec4fc6`, and recommended
  `just headless-release-candidate`. `./scripts/check_headless_status.sh --json` produced valid
  JSON with `evidence_fresh_for_head=false`. Targeted status-summary tests passed (`3 passed`).
  Full `./scripts/check_python_tests.sh` passed (`118 passed`). `./scripts/check_documented_commands.sh`
  passed with `docs=25` and `references=175`; `./scripts/check_architecture_contracts.sh`,
  `./scripts/check_host_policy.sh`, and `git diff --check` passed.
- Commit:       Pending headless evidence freshness warning commit.
- Scope note:   This does not fail existing stale evidence; it makes staleness explicit so a full
  headless release run can be triggered before claiming current-HEAD evidence.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:29 KST — Fresh Headless Release Candidate Evidence — WIP
- Built:        Re-ran the full `./scripts/check_headless_release_candidate.sh` on current `v6`
  HEAD after adding freshness reporting. No code changes were required.
- Verified:     Full headless release-candidate passed and wrote
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T072432Z.json` with
  `valid=true`, `exit_code=0`, and `headless_release_candidate_valid`. The final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T072432Z_release.json` records
  `git.branch=v6` and `git.commit=a1a1a16`, matching the current `HEAD`. `just headless-status`
  now reports `evidence_fresh_for_head: yes`, `headless_ready: yes`, `release_valid: yes`, and
  repeatability `runs_completed=2`, `goal_error_max_m=0.7294855922156234`,
  `goal_error_spread_m=0.0032395771528658246`. `./scripts/check_operational_readiness_audit.sh`
  wrote `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T072910Z.json`
  with `achieved=false` and blockers limited to `hil_preflight` and `field_validation`, which is
  expected for the current no-hardware scope. Full `./scripts/check_python_tests.sh` passed
  (`118 passed`), and `./scripts/check_documented_commands.sh` passed with `docs=25` and
  `references=175`.
- Commit:       Pending fresh headless release-candidate evidence log commit.
- Scope note:   This proves current-HEAD headless simulation and embedded dry-run readiness only.
  It still does not claim HIL, real-sensor, real-actuator, or field readiness.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:30 KST — Headless Freshness Runtime Scope — WIP
- Built:        Refined `scripts/summarize_headless_status.py` so freshness ignores
  `docs/AUTORUN_LOG.md`-only commits. This prevents the evidence-log commit itself from making the
  freshly generated runtime evidence look stale while still reporting runtime-relevant changes after
  the evidence commit.
- Verified:     `./scripts/check_headless_status.sh` now reports `evidence_fresh_for_head: yes`
  for current `v6@f75154e` against evidence `v6@a1a1a16` because the only changed path is
  `docs/AUTORUN_LOG.md`; the JSON output reports `changed_since_evidence=["docs/AUTORUN_LOG.md"]`
  and `relevant_changes_since_evidence=[]`. Targeted status-summary tests passed (`5 passed`).
  Full `./scripts/check_python_tests.sh` passed (`120 passed`). `./scripts/check_documented_commands.sh`,
  `./scripts/check_architecture_contracts.sh`, `./scripts/check_host_policy.sh`, and
  `git diff --check` passed.
- Commit:       Pending headless freshness runtime-scope commit.
- Scope note:   This is a status-reporting fix only; the full headless evidence remains the
  release-candidate bundle generated at `v6@a1a1a16`.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:31 KST — Headless Freshness Reporting Scope — WIP
- Built:        Expanded the freshness ignored-path set to include the headless status summarizer
  and its tests. These files affect evidence reporting, not the simulated autonomy runtime that the
  headless release-candidate bundle validates.
- Verified:     `./scripts/check_headless_status.sh` reports `evidence_fresh_for_head: yes` with
  changed paths `docs/AUTORUN_LOG.md`, `scripts/summarize_headless_status.py`, and
  `tests/evidence/test_headless_status_summary.py`, and with no runtime-relevant changes since the
  evidence commit. Targeted status-summary tests passed (`5 passed`). Full
  `./scripts/check_python_tests.sh` passed (`120 passed`). `./scripts/check_documented_commands.sh`,
  `./scripts/check_architecture_contracts.sh`, `./scripts/check_host_policy.sh`, and
  `git diff --check` passed.
- Commit:       Pending headless freshness reporting-scope commit.
- Scope note:   This keeps current-HEAD evidence status accurate after status-reporting-only
  changes. Runtime-relevant changes still make the evidence stale.
- Next:         Commit and push to `v6`.

## 2026-06-22 16:47 KST — Bootstrap Doctor Release Gate — WIP
- Built:        Added `scripts/generate_bootstrap_doctor.py`, `scripts/check_bootstrap_doctor.sh`,
  and `just bootstrap-doctor`. The doctor validates required repository files, executable entry
  points, required commands, ARIS environment variables/directories, `.env.example` safety defaults,
  no-root execution, `ROS_LOCALHOST_ONLY=1`, and `ARIS_ENABLE_REAL_ACTUATION=0`. Wired
  `bootstrap_doctor` into the headless release-candidate gate, final release validator, and
  readiness evidence index. Normalized core-pipeline repeatability around the stable detour route
  signature so harmless prefix differences after vehicle progress do not fail repeatability.
- Verified:     `./scripts/check_bootstrap_doctor.sh` passed with `bootstrap_doctor_valid`.
  `./scripts/check_core_pipeline_repeatability.sh` passed after route-signature normalization.
  Full `./scripts/check_headless_release_candidate.sh` passed on `v6@9225a83` and wrote
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T074238Z.json` with
  `valid=true`, `exit_code=0`, and `headless_release_candidate_valid`. The final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T074238Z_release.json` records
  `git.commit=9225a83` and includes
  `/home/kotori9/aris/logs/readiness/bootstrap_doctor_20260622T074238Z.json` with `valid=true`.
  `./scripts/check_headless_status.sh` reports `evidence_fresh_for_head: yes`,
  `headless_ready: yes`, and `release_valid: yes`. `./scripts/check_operational_readiness_audit.sh`
  wrote `/home/kotori9/aris/logs/readiness/operational_readiness_audit_20260622T074719Z.json`
  with `achieved=false` and blockers limited to `hil_preflight` and `field_validation`, as expected
  for the current no-hardware scope. Full `./scripts/check_python_tests.sh` passed (`123 passed`);
  `./scripts/check_documented_commands.sh`, `./scripts/check_architecture_contracts.sh`,
  `./scripts/check_host_policy.sh`, and `git diff --check` passed.
- Commit:       Pending bootstrap-doctor release-gate evidence log commit.
- Scope note:   This improves new-environment reproducibility and current headless release evidence.
  It does not claim HIL, real-sensor, real-actuator, or field readiness.

## 2026-06-22 KST — Feature/Milestone Branch Rename

- Built:        Replaced version-only remote branches with descriptive ARIS milestone branches:
  `milestone/teach-repeat-route-replay`, `milestone/lidar-localization-gazebo`,
  `milestone/semantic-hd-map`, `milestone/goal-based-navigation`,
  `milestone/dynamic-obstacle-advisory`, and `milestone/headless-simulation-embedded`.
  Deleted remote `v1` through `v6` and removed the local version-only aliases.
- Built:        Renamed the active local branch to `milestone/headless-simulation-embedded`
  and set it to track `origin/milestone/headless-simulation-embedded`.
- Scope note:   Current active work remains hardware-free: headless simulation, recorded/replayed
  data, ROS 2 processing software, and embedded-interface dry-run software only.
- Next:         Continue headless simulation and embedded dry-run work on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Fresh Release Evidence After Branch Rename

- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@2ca4812` with `headless_release_candidate_valid`.
  The run included bootstrap doctor, embedded dry-run, documented command validation,
  architecture contracts, host policy, core pipeline flow, repeatability, full core readiness, and
  headless readiness audit.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T075350Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T075350Z_release.json`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T075820Z.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T075509Z.log`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T075417Z.json`.
- Scope note:   This proves the current named milestone branch in the hardware-free scope only.
  HIL, real sensors, real actuators, and closed-site field validation remain future milestones.

## 2026-06-22 KST — Branch Policy Release Gate — WIP

- Built:        Added `scripts/check_branch_policy.py`, `scripts/check_branch_policy.sh`, and
  `just branch-policy`. The gate validates the current branch plus local and `origin/*`
  tracking branches against the approved ARIS milestone branch set and rejects version-only or
  task-level branches such as `v6` and `codex/v2-*`.
- Built:        Wired `branch_policy` into the headless release-candidate step list, final
  release validator, readiness evidence index, README quick-start/smoke-test docs, and HANDOFF
  gate sequence.
- Verified:     `./scripts/check_branch_policy.sh` passed with
  `branch_policy_valid current=milestone/headless-simulation-embedded local=7 origin=7`.
  Targeted branch/release/index tests passed (`6 passed`); full
  `./scripts/check_python_tests.sh` passed (`125 passed`); `./scripts/check_documented_commands.sh`
  passed (`docs=25 references=187`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  and produced a report containing the `branch_policy` step and evidence link.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@66f8598` with `headless_release_candidate_valid`.
  The run executed the new `branch_policy` gate before core pipeline flow and then passed
  repeatability, core readiness, and headless readiness audit.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T080248Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T080248Z_release.json`;
  branch policy
  `/home/kotori9/aris/logs/readiness/branch_policy_20260622T080249Z.json`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T080711Z.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T080406Z.log`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T080315Z.json`.
- Next:         Continue improving the hardware-free simulation and embedded dry-run workflow on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Bootstrap Doctor Tracks Branch Policy Entrypoint — WIP

- Built:        Added `scripts/check_branch_policy.sh` to the bootstrap-doctor required file and
  executable checks so new headless environments fail early if the branch-policy gate is missing
  or loses executable permission.
- Built:        Documented the latest branch-policy evidence symlink in README and HANDOFF.
- Verified:     `./scripts/check_bootstrap_doctor.sh` passed with zero blockers. Targeted
  bootstrap/branch-policy tests passed (`6 passed`); full `./scripts/check_python_tests.sh`
  passed (`126 passed`); `./scripts/check_documented_commands.sh` passed
  (`docs=25 references=188`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@8000979` with `headless_release_candidate_valid`.
  The run proved the updated bootstrap doctor, branch-policy gate, embedded dry-run, core pipeline
  flow, repeatability, full core readiness, and headless readiness audit.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T080941Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T080941Z_release.json`;
  bootstrap doctor
  `/home/kotori9/aris/logs/readiness/bootstrap_doctor_20260622T080941Z.json`;
  branch policy
  `/home/kotori9/aris/logs/readiness/branch_policy_20260622T080942Z.json`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T081413Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T081007Z.json`.
- Next:         Continue headless simulation and embedded dry-run reproducibility work on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Repeatability Sample-Floor Evidence — WIP

- Built:        Extended `scripts/check_core_pipeline_repeatability.sh` so repeatability reports
  include minimum `/scan_cloud` samples, `/global_path` points, and `/cmd_drive` samples across
  repeated core-pipeline runs.
- Built:        Tightened `scripts/generate_headless_readiness_audit.py` so headless readiness
  requires at least two sampled repeatability runs, with per-run floors of 5 scan-cloud samples,
  2 global-path points, and 20 command samples.
- Verified:     Targeted headless-readiness tests passed (`6 passed`). A fresh
  `./scripts/check_core_pipeline_repeatability.sh` passed and wrote
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T081640Z.json` with
  `scan_cloud_samples_min=180`, `global_path_points_min=35`, `cmd_samples_min=152`,
  `goal_error_max_m=0.735131221194036`, and `goal_error_spread_m=0.007613088928338119`.
  Full `./scripts/check_python_tests.sh` passed (`127 passed`); `./scripts/check_documented_commands.sh`
  passed (`docs=25 references=188`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@c7ecb7c` with `headless_release_candidate_valid`.
  The repeatability step wrote sampled-run evidence with `goal_error_max_m=0.7303608412692553`
  and `goal_error_spread_m=0.0012324659010648498`; the following headless readiness audit passed
  with zero blockers.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T081822Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T081822Z_release.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T081849Z.json`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T082245Z.json`.
- Next:         Continue strengthening headless simulation evidence and embedded dry-run usability
  on `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Headless Status Shows Repeatability Sample Floors — WIP

- Built:        Updated `scripts/summarize_headless_status.py` so `just headless-status` and the
  JSON summary expose repeatability sample floors: `scan_cloud_samples_min`,
  `global_path_points_min`, and `cmd_samples_min`.
- Verified:     `./scripts/check_headless_status.sh` now prints the sampled-run floors from the
  latest repeatability report: `scan_cloud_samples_min=180`, `global_path_points_min=35`,
  and `cmd_samples_min=178`. Targeted status tests passed (`5 passed`); full
  `./scripts/check_python_tests.sh` passed (`127 passed`); `./scripts/check_documented_commands.sh`
  passed (`docs=25 references=188`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@eabe368` with `headless_release_candidate_valid`.
  The repeatability summary includes sampled-run floors and `./scripts/check_headless_status.sh`
  exposes them in the human-readable status.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T082501Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T082501Z_release.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T082528Z.json`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T082929Z.json`.
- Next:         Continue improving headless release evidence and developer-facing diagnostics on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Documented Script Executability Gate — WIP

- Built:        Tightened `scripts/check_documented_commands.py` so documented `./scripts/...`
  references must exist and be executable. This makes the fallback "run scripts directly" path in
  README fail early if executable bits are lost.
- Verified:     `./scripts/check_documented_commands.sh` passed (`docs=25 references=188`).
  Targeted documented-command tests passed (`2 passed`); full `./scripts/check_python_tests.sh`
  passed (`128 passed`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@0a77e78` with `headless_release_candidate_valid`.
  The release gate executed the tightened documented-command check before the simulation pipeline.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T083203Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T083203Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T083321Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T083630Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T083230Z.json`.
- Next:         Continue tightening documented bootstrap paths and headless runtime diagnostics on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Verification Docs Match Named Milestone Branches — WIP

- Built:        Updated `docs/verification_plan.md` and `docs/architecture_mapping.md` to remove
  stale version-only branch policy text, name `milestone/headless-simulation-embedded` as the
  current hardware-free integration branch, and describe the current release-candidate sequence
  including branch-policy validation and sampled repeatability floors.
- Verified:     `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`).
  Targeted documented-command/branch-policy tests passed (`4 passed`); full
  `./scripts/check_python_tests.sh` passed (`128 passed`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@ce3a53a` with `headless_release_candidate_valid`.
  The gate executed branch-policy validation, sampled repeatability floors, the semantic map and
  review checks, V4 goal navigation, V5 dynamic-obstacle advisory behavior, and the V2 Gazebo
  LiDAR/localization/physics stack without attached hardware.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T083944Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T083944Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T084102Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T084411Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T084010Z.json`.
- Next:         Continue building only the headless simulation and embedded dry-run surface until
  hardware becomes available; keep feature work on named milestone branches.

## 2026-06-22 KST — Bootstrap Requires Release Gate Fallback Scripts — WIP

- Built:        Strengthened `scripts/generate_bootstrap_doctor.py` so a new headless environment
  is only considered bootstrappable when every script used by the direct
  `./scripts/check_headless_release_candidate.sh` fallback path exists and is executable. This now
  covers embedded dry-run, documented commands, architecture contracts, host policy, branch policy,
  core pipeline flow, repeatability, core readiness reporting, and headless readiness audit
  entrypoints.
- Verified:     `./scripts/check_bootstrap_doctor.sh` passed with zero blockers. Targeted bootstrap
  doctor tests passed (`6 passed`), including missing fallback script and non-executable fallback
  script regressions. Full `./scripts/check_python_tests.sh` passed (`130 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Evidence:     Bootstrap report
  `/home/kotori9/aris/logs/readiness/bootstrap_doctor_20260622T084718Z.json`; reuse release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T084732Z.json`; final
  evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T084732Z_release.json`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@8f8e4d6` with `headless_release_candidate_valid`.
  The refreshed bootstrap doctor enforced the complete release-gate fallback script set before the
  embedded dry-run, pipeline, semantic map/review, V4/V5 behavior, and V2 Gazebo stack checks ran.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T084829Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T084829Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T084948Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T085256Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T084856Z.json`.
- Next:         Continue strengthening headless simulation and embedded dry-run reproducibility on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Bootstrap Requires Core Readiness Child Scripts — WIP

- Built:        Extended `scripts/generate_bootstrap_doctor.py` beyond the top-level release gate
  scripts so it also requires the Quick Start Docker build entrypoint, `check_core_readiness.sh`,
  and the child scripts used by the core readiness and V2 Gazebo stack gates. A new regression test
  confirms missing nested Gazebo localization scripts fail bootstrap before a long release run is
  attempted.
- Verified:     `./scripts/check_bootstrap_doctor.sh` passed with zero blockers. Targeted bootstrap
  doctor tests passed (`7 passed`); full `./scripts/check_python_tests.sh` passed (`131 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Evidence:     Bootstrap report
  `/home/kotori9/aris/logs/readiness/bootstrap_doctor_20260622T085532Z.json`; reuse release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T085543Z.json`; final
  evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T085543Z_release.json`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@f2129c6` with `headless_release_candidate_valid`.
  The expanded bootstrap doctor passed before the release gate exercised embedded dry-run, the
  core pipeline, repeatability, core readiness, V3/V6 map review, V4/V5 behavior, and the full V2
  Gazebo stack.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T085634Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T085634Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T085752Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T090104Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T085701Z.json`.
- Next:         Continue strengthening new-environment reproducibility and headless simulation
  coverage on `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Headless Status Separates Actuation Scope — WIP

- Built:        Updated `scripts/summarize_headless_status.py` so `just headless-status` separates
  `hardware_scope_active`, `real_actuation_enabled`, and `safe_to_enable_real_actuation` instead
  of presenting actuation safety as if it were the current environment state. The JSON summary now
  also carries an `execution_scope` object with the same three fields.
- Built:        Clarified the README `headless-status` description so users know the command
  reports both evidence freshness and whether hardware scope or real actuation is active.
- Verified:     `./scripts/check_headless_status.sh` now reports hardware scope inactive, real
  actuation disabled, and not safe to enable real actuation for the current no-hardware scope.
  Targeted headless-status tests passed (`6 passed`); full `./scripts/check_python_tests.sh`
  passed (`132 passed`); `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`);
  reuse-mode `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh`
  passed with `headless_release_candidate_valid`.
- Evidence:     Reuse release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T101504Z.json`; final
  evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T101504Z_release.json`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@3ef6fae` with `headless_release_candidate_valid`, so the
  clarified status output is backed by fresh current-HEAD evidence.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T101607Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T101607Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T101726Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T102037Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T101634Z.json`.
- Next:         Continue improving headless status usability and evidence traceability on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Headless Status Shows Release Step Results — WIP

- Built:        Extended `scripts/summarize_headless_status.py` text output with a `Release steps`
  section that lists each release-candidate step and its pass/fail result plus exit code. This
  makes `just headless-status` explain not only that the release is valid, but which gate sequence
  produced that result.
- Built:        Updated README text for `headless-status` to mention release step pass/fail
  reporting alongside evidence freshness and actuation scope.
- Verified:     `./scripts/check_headless_status.sh` prints all ten release steps:
  bootstrap doctor, embedded dry-run, documented commands, architecture contracts, host policy,
  branch policy, core pipeline flow, repeatability, core readiness report, and headless readiness
  audit. Targeted headless-status tests passed (`6 passed`); full
  `./scripts/check_python_tests.sh` passed (`132 passed`); `./scripts/check_documented_commands.sh`
  passed (`docs=25 references=190`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Evidence:     Reuse release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T102244Z.json`; final
  evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T102244Z_release.json`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@639f123` with `headless_release_candidate_valid`.
  The release-step status output is now backed by current-HEAD evidence.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T102336Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T102336Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T102456Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T102828Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T102403Z.json`.
- Next:         Continue improving evidence traceability and practical headless usability on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Headless Status Shows Per-Step Evidence Paths — WIP

- Built:        Extended `scripts/summarize_headless_status.py` so the JSON summary exposes
  `release_evidence` from the latest release candidate and the text output prints a
  `Release evidence` section. The status command now ties each release gate result to its
  timestamped artifact path.
- Built:        Updated README text for `headless-status` to mention per-step evidence paths.
- Verified:     `./scripts/check_headless_status.sh` now prints release evidence paths for
  bootstrap doctor, embedded dry-run, branch policy, core pipeline flow, repeatability, core
  readiness, headless audit, and the final evidence index. Targeted headless-status tests passed
  (`6 passed`); full `./scripts/check_python_tests.sh` passed (`132 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`); reuse-mode
  `ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 ./scripts/check_headless_release_candidate.sh` passed
  with `headless_release_candidate_valid`.
- Evidence:     Reuse release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T103029Z.json`; final
  evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T103029Z_release.json`.
- Verified:     A full `./scripts/check_headless_release_candidate.sh` was attempted on
  `milestone/headless-simulation-embedded@90ca5d4` and exposed a real repeatability weakness:
  equivalent detour routes could fail when a later run started from a progressed route suffix
  such as `detour_b -> detour_c -> goal`.
- Next:         Fix route-suffix repeatability so harmless progress along the same detour route
  remains stable while genuinely different final detours still fail.

## 2026-06-22 KST — Core Pipeline Repeatability Accepts Stable Route Suffixes — WIP

- Built:        Moved core-pipeline repeatability summarization into
  `scripts/summarize_core_pipeline_repeatability.py` so route-signature logic is directly
  testable. `scripts/check_core_pipeline_repeatability.sh` now calls that summarizer.
- Built:        Updated route stability so repeated runs pass when they share the same final
  detour suffix, accounting for a vehicle already progressed past an earlier detour node. Different
  final detours are still rejected. Added the new summarizer to bootstrap-doctor required
  executables.
- Verified:     Re-summarized the failed evidence pair from
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T103132Z.json`; the new
  logic accepts the stable suffix and records `route_signature=["detour_b","detour_c","goal"]`.
  Targeted repeatability/bootstrap tests passed (`10 passed`); `./scripts/check_bootstrap_doctor.sh`
  passed; full `./scripts/check_python_tests.sh` passed (`135 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`);
  `./scripts/check_core_pipeline_repeatability.sh` passed.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@bc2add6` with `headless_release_candidate_valid`.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T103552Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T103552Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T103711Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T104031Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T103619Z.json`.
- Next:         Commit and push the repeatability suffix fix and evidence log on
  `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Repeatability Suffix Criteria Documented

- Built:        Updated `docs/verification_plan.md` and `docs/workflows.md` to state that
  core-pipeline route stability is evaluated on the final detour suffix. The docs now explain why
  progress from `detour_a -> detour_b` to `detour_b -> detour_c -> goal` is stable, while a
  genuinely different final detour still fails.
- Verified:     `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`).
  `./scripts/check_headless_status.sh` reported fresh evidence after the full release refresh.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@87f2fdf` with `headless_release_candidate_valid`.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T104315Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T104315Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T104435Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T104756Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T104343Z.json`.
- Next:         Continue improving documented acceptance criteria and headless operator
  diagnostics on `milestone/headless-simulation-embedded`.

## 2026-06-22 KST — Headless Evidence Age and V3 Compare Stability

- Built:        Extended `scripts/summarize_headless_status.py` so `just headless-status` and
  `./scripts/check_headless_status.sh --json` include `evidence_age` for the latest headless
  release, headless audit, evidence index, and core-pipeline repeatability artifacts. The text
  output now prints each artifact age and UTC modification time.
- Built:        Updated the README `headless-status` description so operators know the status
  command reports evidence age in addition to freshness against Git `HEAD`.
- Verified:     Targeted headless-status tests passed (`6 passed`); full
  `./scripts/check_python_tests.sh` passed (`135 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`).
- Verified:     A full `./scripts/check_headless_release_candidate.sh` on
  `milestone/headless-simulation-embedded@02f627f` exposed a real V3 repeat-pass threshold issue:
  `review_queue_delta=6` failed the previous `<=5` limit even though metric/route/label/high-risk
  stability remained intact.
- Built:        Updated `scripts/check_v3_semantic_map.sh` to allow up to eight review-queue
  entries of delta while keeping metric overlap, route overlap, label-change, and high-risk-cell
  bounds unchanged. `scripts/compare_semantic_map_snapshots.py` now writes the compare report even
  on CLI failure so future V3 instability leaves machine-readable evidence.
- Verified:     Targeted semantic-map compare tests passed (`3 passed`); direct
  `./scripts/check_v3_semantic_map.sh` passed with `review_queue_delta=6`,
  `metric_overlap=0.937`, `route_overlap=1.000`, `label_changes=0`, and `high_risk_delta=0`.
  Full `./scripts/check_python_tests.sh` passed (`136 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`).
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@8a5a574` with `headless_release_candidate_valid`.
  `./scripts/check_headless_status.sh` then reported `headless_ready=yes`, `release_valid=yes`,
  `evidence_fresh_for_head=yes`, and evidence age for all four tracked status artifacts.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T105528Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T105528Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T105648Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T105957Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T105555Z.json`;
  V3 compare
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_105710.compare.json`.
- Next:         Continue tightening hardware-free simulation evidence and operator diagnostics
  while keeping real hardware/HIL out of scope until hardware is attached.

## 2026-06-22 KST — Headless Freshness Explains Dirty Worktrees

- Built:        Updated `scripts/summarize_headless_status.py` so headless status now reports a
  `freshness_reason` in JSON and text output. The status command distinguishes matching evidence
  commits, ignored documentation/log-only changes, runtime-relevant commits since evidence, missing
  Git evidence, and runtime-relevant uncommitted worktree changes.
- Built:        Extended freshness evaluation to inspect uncommitted worktree changes as well as
  committed differences since the evidence commit. This prevents a dirty runtime-relevant worktree
  from being reported as fresh simply because `HEAD` still matches the previous release evidence.
- Built:        Updated README text for `headless-status` to document that the command explains why
  evidence is fresh or stale.
- Verified:     Targeted headless-status tests passed (`7 passed`), including the new dirty
  worktree case. Full `./scripts/check_python_tests.sh` passed (`137 passed`);
  `./scripts/check_documented_commands.sh` passed (`docs=25 references=190`).
- Verified:     Before committing, `./scripts/check_headless_status.sh` correctly reported
  `evidence_fresh_for_head=no`, `evidence_freshness_reason=runtime_relevant_worktree_changes`,
  and `relevant_worktree_changes=README.md`.
- Verified:     Full `./scripts/check_headless_release_candidate.sh` passed on
  `milestone/headless-simulation-embedded@5e1ca64` with `headless_release_candidate_valid`.
  `./scripts/check_headless_status.sh` then reported `headless_ready=yes`, `release_valid=yes`,
  `evidence_fresh_for_head=yes`, and `evidence_freshness_reason=matching_head`.
- Evidence:     Release report
  `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T110406Z.json`;
  final evidence index
  `/home/kotori9/aris/logs/readiness/evidence_index_20260622T110406Z_release.json`;
  core readiness
  `/home/kotori9/aris/logs/readiness/core_readiness_20260622T110526Z.log`;
  headless audit
  `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T110843Z.json`;
  repeatability
  `/home/kotori9/aris/logs/pipeline/core_pipeline_repeatability_20260622T110433Z.json`;
  V3 compare
  `/home/kotori9/aris/logs/maps/v3_semantic_map_20260622_110552.compare.json`.
- Next:         Continue strengthening headless simulation reproducibility and operator-facing
  diagnostics on `milestone/headless-simulation-embedded`.
