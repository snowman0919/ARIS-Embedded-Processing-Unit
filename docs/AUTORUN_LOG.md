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
- Commit:       Pending V5 persistent obstacle track evidence commit.
- Stubbed/blocked: This is a nearest-neighbor single-corridor tracker for simulation evidence. It
  is not yet a production multi-object tracker, static-map differencer, route-graph replan scorer,
  real LiDAR replay gate, HIL, or field validation.
- Next:         Commit and push the tracking increment to `origin/v3`; then add recorded/replayed
  obstacle-bag scoring and route-graph replan evidence.
