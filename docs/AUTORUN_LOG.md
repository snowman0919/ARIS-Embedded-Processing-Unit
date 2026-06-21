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
