# ARIS Handoff

This document is the current continuation guide for ARIS development. It supersedes older V0/V1
handoff notes.

## Current State

- Repository: `ARIS-Embedded-Processing-Unit`, local path `/home/sbeen/aris/aris-dev-env`.
- Active milestone branch: `v6`.
- Remote branch policy: keep ARIS milestone branches only (`v1` through `v6` plus `main`).
- Current execution scope: headless simulation, recorded/replayed data, ROS 2 processing software,
  and embedded-interface dry-run software.
- No vehicle hardware is attached. HIL and field validation are future evidence contracts, not
  active blockers for headless work.

## What Is Proven In Headless Scope

The latest verified hardware-free release-candidate bundle is:

```bash
just headless-release-candidate
```

It runs these gates in sequence:

1. `just embedded-dry-run`
2. `just documented-commands`
3. `just architecture-contracts`
4. `just host-policy`
5. `just core-pipeline-flow`
6. `just core-pipeline-repeatability`
7. `just core-readiness-report`
8. `just headless-readiness-audit`

After those steps, `scripts/validate_headless_release_candidate.py` checks that the final release
report includes every required step, points at the final evidence index, and that the final index
points back to the release report.

The most recent full run passed and wrote:

- `/home/kotori9/aris/logs/readiness/headless_release_candidate_20260622T064544Z.json`
- `/home/kotori9/aris/logs/readiness/headless_readiness_audit_20260622T064914Z.json`
- `/home/kotori9/aris/logs/readiness/evidence_index_20260622T064927Z.json`

The current `headless_ready` result is true for the hardware-free scope. This is not real-actuation
readiness.

## Core Pipeline Evidence

The cross-milestone flow is verified by:

```bash
just core-pipeline-flow
```

It proves, in one bounded headless run:

```text
Mapping -> Semantic HD Map -> Route Graph -> Localization -> Goal Based Planning -> Autonomous Driving
```

The gate creates a `SemanticHDMap` snapshot, validates its semantic and route-graph layers, launches
the V4 planner with that snapshot as `semantic_map_file`, observes LiDAR localization, publishes
`/global_path`, and verifies moving `/cmd_drive` samples.

## Hard Rules

- Do not use `sudo` or host `apt`.
- Do not modify `/etc`, systemd, udev, kernel modules, Docker daemon config, or global package
  state.
- Keep real actuation disabled unless a future hardware milestone explicitly requires and validates
  it.
- Preserve the control contract:

```text
planner or teleop -> /cmd_drive -> HAL -> simulator or STM32
```

- AI/advisory code must not publish `/cmd_drive`, clear faults, release E-stop, or enable
  actuation.
- Prefer Nix and repo scripts/Just targets for reproducibility.
- Commit and push meaningful changes to the relevant ARIS milestone branch, currently `v6`.

## Primary Commands

Enter the development shell:

```bash
nix develop
```

Build and test:

```bash
just docker-build
just ros2-build
just python-test
just documented-commands
just architecture-contracts
just host-policy
just core-readiness-report
just core-pipeline-flow
just core-pipeline-repeatability
just headless-status
just headless-release-candidate
```

Fast evidence-index closure check using existing latest evidence:

```bash
ARIS_HEADLESS_RELEASE_REUSE_EXISTING=1 just headless-release-candidate
```

This reuse mode is only for report/index plumbing. Normal `just headless-release-candidate` runs the
full evidence bundle.

## Evidence Locations

Runtime artifacts live outside the Git tree under `$ARIS_LOGS`, normally `/home/kotori9/aris/logs`.

Important latest symlinks:

- `$ARIS_LOGS/readiness/latest_headless_release_candidate.json`
- `$ARIS_LOGS/readiness/latest_headless_readiness_audit.json`
- `$ARIS_LOGS/readiness/latest_evidence_index.json`
- `$ARIS_LOGS/pipeline/latest_core_pipeline_flow.json`
- `$ARIS_LOGS/embedded/latest_embedded_dry_run.json`

For a quick human-readable status from those latest artifacts:

```bash
just headless-status
```

## Remaining Scope

The full project goal is not complete. Remaining work for practical real-world use includes:

- Real Unitree L2 LiDAR driver/data validation.
- Production localization beyond the current headless Gazebo/surrogate evidence.
- Real or representative camera streams and segmentation for production semantic mapping.
- Hardware serial/CAN transport and STM32 bench validation.
- Closed-site field validation with operator approvals.
- GUI/operator map viewer, goal selection, monitoring, and review UX.

Until hardware is attached, continue improving headless simulation, recorded/replayed evidence,
embedded-interface dry-runs, documentation, and release-candidate reproducibility on `v6`.

## Update Discipline

For every meaningful change:

1. Keep code, scripts, tests, and docs aligned.
2. Run the smallest relevant tests plus broader gates when the change affects shared behavior.
3. Append a dated entry to `docs/AUTORUN_LOG.md` with built, verified, commit, scope, and next step.
4. Commit with the configured author `snowman0919 <dbsgur123321@gmail.com>`.
5. Push to the current milestone branch.
