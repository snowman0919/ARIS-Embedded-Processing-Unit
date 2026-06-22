# ARIS — Handoff / Continuation Prompt for a Coding Agent

> You are taking over development of **ARIS**, a simulation-first autonomous-driving
> research platform. This document is self-contained — read it fully before acting.
> The previous agent built the interface-contract foundation and the **V0** milestone.
> Your job is to continue (next: **V1**, see §8) **without breaking the hard rules in
> §2 or the interface contract in §4.**
>
> **Running unattended (overnight autonomous run)? Read §10 first.** Work through
> **V1 → V6 in order**, verifying each against its completion criteria, checkpointing with
> local commits (no push), and logging to `docs/AUTORUN_LOG.md`. **Never fake a milestone's
> completion** — a build that compiles is not "done".

---

## 1. TL;DR — current state (as of 2026-06-21)

- **Repo:** `~/aris/aris-dev-env` — a Nix + Docker workspace, ROS 2 Jazzy, targeting **NVIDIA
  DGX Spark (aarch64)**. Runtime data/logs/models live **outside** the repo at `~/aris`
  (`ARIS_HOME`); the repo stays clean.
- **Done & verified:** the §4 **invariant interface contract** (`/cmd_drive` + HAL + TF +
  one URDF) and **V0** (manual teleop driving + the `aris_bringup` `use_sim`/`mode` launch
  switch + rosbag recording). `ros2-build` is green (7 packages); integration smoke and
  **13 unit tests** pass.
- **Important:** the "simulator" today is a lightweight **Python kinematic-bicycle node**,
  **not Gazebo**. Real physics + sensors (LiDAR/cameras) are deferred to V2/V3.
- **Next milestone:** **V1 — teach-and-repeat** (§8).
- **Git:** one initial commit on branch `main`; a GitHub upload was in progress (pending the
  owner's `gh auth login`).

---

## 2. HARD RULES — do not violate

1. **All development goes through Nix.** Run every tool as `nix develop -c just <recipe>`
   (or enter `nix develop`, then `just`). **Never** call `docker`, `colcon`, or `ros2`
   directly on the host. Docker is still the runtime for ROS2/AI/embedded, but you enter it
   via the Nix shell + `just`/`scripts`. (This is an explicit owner directive.)
2. **No sudo, no host apt, no touching `/etc`·systemd·udev·docker-daemon** (see `AGENTS.md`).
   To add a system/ROS package, edit the relevant `docker/*.Dockerfile` and rebuild the image
   (`nix develop -c just docker-build`).
3. **Never break the §4 interface contract.** Every driving algorithm's final output is
   `/cmd_drive` (`ackermann_msgs/AckermannDriveStamped`). No node may know whether it runs in
   sim or on the real car — sim/real differ **only** at the HAL edges.
4. **Simulation-safe by default.** Real actuation is gated behind
   `ARIS_ENABLE_REAL_ACTUATION=1`; keep it off. The STM32 bridge stays dry-run.
5. **Pure core / ROS wrapper split.** Put algorithms in ROS-free modules (`*_core.py`,
   unit-tested); keep ROS nodes (`*_node.py`) thin. Externalize params to launch/YAML — no
   hardcoded constants that must differ between sim and real.
6. The canonical context is the Korean master design spec ("ARIS Gazebo-first & Sim2Real
   설계서", roadmap V0→V6). Don't regress an earlier milestone's completion criteria.

---

## 3. Environment & commands (everything via Nix)

```bash
cd ~/aris/aris-dev-env
nix develop -c just ros2-build      # colcon build in the ROS2 container
nix develop -c just auto-sim        # smoke: autonomous stack launches ~12s (exit 124 = ok)
nix develop -c just teleop          # V0: bring up sim stack in teleop mode
nix develop -c just teleop-key      # V0: keyboard -> /cmd_vel (run in a 2nd terminal)
nix develop -c just record          # V0: rosbag of contract topics -> ~/aris/logs/bags/
nix develop -c just protocol-test   # host pytest (MCU binary protocol)
nix develop -c just docker-build    # rebuild containers after a Dockerfile edit
```

Run the unit tests inside the container:

```bash
nix develop -c ./scripts/run_ros2.sh bash -lc 'source install/setup.bash && python3 -m pytest src -q'
```

> **Verification-scripting tip (learned the hard way):** when you launch nodes in a
> background shell for a smoke test, do **not** use a bare `wait` — it hangs on un-reaped
> `ros2 launch` children. Bound each launch with `timeout -s INT N ros2 launch ...`, and stop
> `ros2 bag record` with **SIGINT** so it writes `metadata.yaml` (a `kill -9`'d bag has no
> metadata and is unreadable).

---

## 4. The invariant interface contract (§4 of the spec) — DO NOT BREAK

**Topics**

| topic | type | direction |
|---|---|---|
| `/cmd_drive` | `ackermann_msgs/AckermannDriveStamped` | planner/teleop → HAL (the one control contract) |
| `/odometry/filtered` | `nav_msgs/Odometry` | localization → planner (**V1: sim publishes a placeholder**) |
| `/wheel_odom` | `nav_msgs/Odometry` | odometry source (sim) |
| `/vehicle/state` | `aris_interfaces/StateReport` | MCU bridge → system |
| `/estop` | `std_msgs/Bool` | safety |
| `/cmd_vel` | `geometry_msgs/Twist` | teleop input → `teleop_node` |

Sensor topics `/scan_cloud`, `/imu/data`, `/gps/fix`, `/camera/{front,fl,fr,left,right,rear}/image`
arrive with the Gazebo sensor suite at V2/V3.

**TF tree:** `map → odom → base_link → {lidar_link, camera_*_link, imu_link, gps_link}`.
`odom→base_link` from odometry (the sim today); `map→odom` from localization (**V1: a static
identity placeholder**); `base_link→sensors` from the URDF via `robot_state_publisher`.

**Data flow today**

```
teleop_node OR local_planner ──/cmd_drive──┬─▶ vehicle_sim_node (sim HAL) ─▶ /wheel_odom + /odometry/filtered + TF(odom→base_link)
                                           └─▶ mcu_bridge_node (STM32 HAL, dry-run) ─▶ binary CMD_CONTROL + /vehicle/state + /estop
```

---

## 5. Packages (repo names differ from the spec's — mapping noted)

| package | role | key files | spec name |
|---|---|---|---|
| `aris_description` | single shared URDF/xacro (L=1.25, max_steer=0.6, sensor extrinsics) + `robot_state_publisher` | `urdf/aris.urdf.xacro`, `launch/description.launch.py` | aris_description |
| `aris_interfaces` | rosidl custom msgs | `msg/StateReport.msg` | aris_msgs |
| `aris_bringup` | the `use_sim:=true\|false mode:=teleop\|auto` switch, teleop bridge, recording | `launch/bringup.launch.py`, `teleop_node.py`, `teleop_core.py`, `launch/record.launch.py` | aris_bringup |
| `aris_vehicle_sim` | **sim HAL**: `/cmd_drive` → kinematic bicycle → odom + TF | `vehicle_sim_node.py`, `kinematic_bicycle.py` (pure) | aris_sim |
| `aris_mcu_bridge` | **STM32 HAL**: `/cmd_drive` → binary frames (dry-run) + heartbeat + `/vehicle/state` | `bridge_node.py`, `protocol.py` (pure) | aris_hal/stm32_bridge |
| `aris_planning` | local planner (`/odometry/filtered` → `/cmd_drive`) | `local_planner_node.py`, `pure_pursuit.py` (pure), `astar.py` (pure), `cmd_drive.py` (pure) | aris_planning |

Stubs (README-only, built in later V's): `aris_localization` (V2), `aris_mapping` (V2–3),
`aris_perception` (V3,V5), `aris_gui`, `aris_ai_semantics` (V6 multimodal).
Firmware: `firmware/stm32f446_safety_mcu` (Rust, `COLCON_IGNORE`).

> Legacy: `aris_mcu_bridge/bridge_sim.py` is a standalone dry-run loop **superseded** by
> `bridge_node.py`; safe to remove when convenient.

---

## 6. Known placeholders & gotchas (replace as the relevant V arrives — these are NOT final)

- **Sim is a Python kinematic node, not Gazebo.** No real physics/sensors. Standing up Gazebo
  Harmonic (`ros_gz`) with the URDF spawned + `gpu_lidar` is a V2 task (note: `gpu_lidar` needs
  GPU rendering; the host is a headless DGX Spark — see the spec's rendering caveats).
- **`/odometry/filtered` is published by the sim as a V1 ground-truth placeholder**, and
  **`map→odom` is a static identity** (`static_transform_publisher` in `bringup.launch.py`). At
  V2 the real `aris_localization` (EKF + NDT) must take over **both**, and the sim should then
  publish only `/wheel_odom` + sensors.
- **The planner follows a hardcoded sine demo path** (`local_planner_node.py`). V1 replaces it
  with a recorded route (§8).
- **Real-mode HAL (`use_sim:=false`) is a documented stub** — no LiDAR/camera drivers or STM32
  serial transport yet (`bridge_node._control_tick` has `TODO(real-hal)`).
- URDF sensor extrinsics are initial estimates; real LiDAR↔camera calibration updates the same
  file (so sim and real stay identical).

---

## 7. How to verify you didn't break anything

`nix develop -c just ros2-build` (must stay green) → `nix develop -c just auto-sim` (stack
launches, no crash) → unit tests (§3, currently 13 passing). For functional checks, launch and
introspect: `ros2 topic echo --once /cmd_drive`, `... /vehicle/state`, and
`ros2 run tf2_ros tf2_echo map base_link`.

---

## 8. NEXT TASK — V1: Teach-and-Repeat

**Goal:** drive a previously-recorded trajectory — the simplest autonomy, no localization yet.
Build on the contract; **do not change `/cmd_drive`** or the pure `PurePursuit` core's behavior.

- **Teach:** add `aris_planning/path_recorder_node.py` — subscribe `/odometry/filtered`, append a
  waypoint every ~0.2 m to a `route.csv` with columns `x, y, yaw, v_target`. Save under
  `~/aris/data/routes/` (`ARIS_DATA`). Add a `just`/launch entry to run it.
- **Repeat:** give `local_planner_node.py` a `route_file` parameter; when set, load `route.csv`
  instead of the hardcoded sine path and follow it with the existing `PurePursuit`.
- **Keep the pure/ROS split:** put CSV loading + waypoint selection in a ROS-free
  `aris_planning/route.py` core with unit tests (mirror `cmd_drive.py` + its tests).
- **Completion criteria (from the spec):** in sim, record a teleop run, then repeat it tracking
  within **±0.3 m** lateral error. Odometry-only drift will accumulate — expected; fixed at V2.
- **Suggested flow:** `just teleop` + `just teleop-key` to drive while `path_recorder` records →
  then launch repeat mode and compare.

**After V1:** V2 = LiDAR localization (EKF + NDT producing the real `/odometry/filtered` and
`map→odom`), which also forces standing up Gazebo + `gpu_lidar` for `/scan_cloud`.

---

## 9. Reference

- **Roadmap:** V0 ✅ → **V1 (next)** → V2 localization → V3 semantic HD map → V4 goal-based nav
  (Nav2) → V5 dynamic-obstacle avoidance → V6 multimodal (offline, Cosmos 3 — **never** in the
  control loop).
- `AGENTS.md` (host hard rules), `README.md` (env setup), `docs/*.md` (subsystem notes),
  `docs/mcu_protocol.md` (STM32 binary protocol).
- Ask the owner for the full Korean master design spec PDF if you need the deep rationale
  (Sim2Real gaps, the five-layer semantic map, cost models, etc.).

---

## 10. AUTONOMOUS UNATTENDED RUN — complete as much of V1→V6 as you correctly can

This run is **unattended** (the owner is asleep). Goal: maximize *correct, verified* progress
through the roadmap **in order**, and leave a trail the owner can resume from in one read.

> **Realistic expectation:** V1 is achievable tonight. V2+ get progressively harder and several
> stages need external assets that may **not** exist in this environment — V2 needs Gazebo GPU
> rendering of a `gpu_lidar` (headless DGX Spark may not render), V3/V5 need camera perception
> **models + data**, V6 needs the **Cosmos 3** model. When genuinely blocked, **document it and
> stop — do not fake completion.** A partial-but-honest result is the success condition here.

### Operating loop — repeat for V1, then V2, … V6
1. Implement the milestone per its spec (obey §2 hard rules and the §4 contract).
2. Build green: `nix develop -c just ros2-build`.
3. Verify the milestone's **completion criteria** (below / §8). Use **bounded** smoke tests
   (`timeout -s INT N ros2 launch …`; **never a bare `wait`** — it hangs).
4. Run the unit tests; add ROS-free `*_core` tests for new logic.
5. **Checkpoint with a LOCAL commit** (GitHub is intentionally skipped — **no `git push`**):
   `nix develop -c git commit -am "Vx: <what> (verified: <how>)"`.
6. Append a dated entry to `docs/AUTORUN_LOG.md` (built / verified-with-numbers / commit /
   stubbed-or-blocked / next). Then go to the next milestone.

### Gates & honesty rules — DO NOT VIOLATE
- A milestone is **done only when its real completion criteria pass**. Never disable, delete, skip,
  or weaken tests; never hardcode outputs to make a check pass. A compiling build is **not** done.
- If **blocked** (missing model / dataset / GPU rendering / hardware): (a) write the blocker clearly
  in `docs/AUTORUN_LOG.md`; (b) implement the maximum *clean, clearly-labelled* scaffold you safely
  can (with `TODO`s and tests for the parts that genuinely work) and commit it as **WIP**; (c) if the
  next milestone hard-depends on the blocked one, **stop forward progress** and instead harden, test,
  and document what exists. **Never skip a dependency to chase a later milestone.**
- **Simulation-safe always:** never set `ARIS_ENABLE_REAL_ACTUATION=1`; no real actuation.
- **Safety:** no `sudo`, no host-system changes, no destructive commands (`rm -rf` outside
  `build/ install/ log/`), **no `git push`/remote writes**, never delete `~/aris` data or rosbags.
  Every launch/smoke must self-terminate via `timeout` — start no unbounded background process.
- If the **same error** persists past a few attempts, stop thrashing: log it and switch to hardening
  and documenting what already works.

### Milestone specs (summaries — full rationale in the master spec)
- **V1 — Teach-and-Repeat** (see §8). Completion: replay a recorded route within **±0.3 m** in sim.
- **V2 — LiDAR Localization.** Stand up Gazebo Harmonic (`ros_gz`) with the URDF spawned + a
  `gpu_lidar` publishing `/scan_cloud` (⚠️ GPU rendering — if it won't render headless, that is the
  blocker; record it). Build a map once (SLAM → `.pcd`), then EKF (`robot_localization`) fusing wheel
  odom + IMU + NDT scan-matching → **real** `/odometry/filtered` and `map→odom`, replacing the V1
  placeholders, in `aris_localization`. Completion: ≤5 cm lateral error, no long-run drift; V1 repeat
  still works unchanged on the new `/odometry/filtered`.
- **V3 — Semantic HD Map.** 5 layers (metric/occupancy/semantic/traversability/route-graph), camera
  segmentation projected by pose, repeat-pass confidence + change detection (`aris_mapping`,
  `aris_perception`). ⚠️ needs a segmentation model + camera streams — likely blocked; scaffold the
  layer structs + update policy as pure cores **with tests**, and document the model gap.
- **V4 — Goal-Based Navigation.** Global planner (A*/Dijkstra on the route graph — reuse `astar.py` —
  or Nav2 Smac + controller) with a semantic cost model → `/global_path`; the local Pure-Pursuit
  follows it. Completion: enter a goal → path → arrive within tolerance, avoiding no-go/semantic
  penalties.
- **V5 — Dynamic Obstacle Avoidance.** Static/dynamic split (scan vs map diff), tracker (id+velocity),
  avoidance FSM (watch/slow/offset/stop by distance + TTC); spawn actors in sim. Completion: zero
  collisions in crossing-pedestrian / stopped-vehicle scenarios. Safe fallback: unclassified dynamic
  obstacle ⇒ stop/avoid.
- **V6 — Multimodal Semantic Update (offline).** Cosmos 3 pipeline for change-review / event
  explanation. **Never** in the control loop — outputs only annotate the map. ⚠️ needs the model;
  scaffold the offline pipeline interface + document the model gap.

### Finish condition
Whether you complete everything or hit a wall, make sure `docs/AUTORUN_LOG.md` ends with a clear
**summary**: which V's are truly done (criteria passed), which are WIP/blocked and why, the exact
next step, and the current build/test state — so the owner resumes in one read.
