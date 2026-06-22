# Environment

The host environment is intentionally small and user-space only.

- Host tools come from Nix.
- Heavy runtimes run inside Docker.
- Data, logs, models, and caches live under `ARIS_HOME`, defaulting to `~/aris`.
- Default ROS2 traffic is local-only with `ROS_LOCALHOST_ONLY=1`.
- The current active scope is headless simulation and embedded dry-run software. No serial, CAN,
  camera, LiDAR, actuator, or vehicle bench hardware is assumed to be attached.

Enter the environment:

```bash
nix develop
```

Then inspect:

```bash
just nix-shell-info
```

## Reproducible Headless Bootstrap

From a fresh checkout, the first software-only gate is:

```bash
just bootstrap-doctor
```

This verifies the repository files, executable scripts, Nix/Docker host commands, ARIS path
variables, local-only ROS defaults, and disabled real actuation. A valid bootstrap doctor means the
workspace can run the heavier headless simulation and embedded dry-run checks without asking for
host sudo or attached hardware.

The current branch set should also match the ARIS milestone policy:

```bash
just branch-policy
```

The expected remote branch shape is `main` plus ARIS `v{num}-{context}` baselines. Task branches
such as `codex/*`, version-only branches such as `v6`, and stale `milestone/*` branches should not
remain on origin.

## Evidence-Producing Run

The full hardware-free release-candidate command is:

```bash
just headless-release-candidate
```

It runs the bootstrap, embedded dry-run, documented-command, architecture-contract, host-policy,
branch-policy, six-stage core pipeline, repeatability, core-readiness report, and headless audit
checks in sequence. The run writes timestamped evidence under `$ARIS_LOGS/readiness/` and updates:

```text
$ARIS_LOGS/readiness/latest_headless_release_candidate.json
$ARIS_LOGS/readiness/latest_headless_status.json
$ARIS_LOGS/readiness/latest_evidence_index.json
```

Inspect the latest bundle with:

```bash
just headless-status
```

For automation or handoff, use the JSON form:

```bash
./scripts/check_headless_status.sh --json
```

The status summary reports whether the latest release evidence is fresh for the current Git `HEAD`,
whether `origin/main` and `origin/v6-headless-simulation-embedded` are synchronized, whether the
local branch is ahead of or behind its upstream, and whether real actuation is still disabled.

## Interpreting Common Failures

- `bootstrap-doctor` failing on a missing command usually means the shell is not inside
  `nix develop`, or Docker is not available to the current user session.
- `branch-policy` failing means local or remote branches need to be pruned back to `main` and the
  ARIS milestone branches listed in `docs/verification_plan.md`.
- `headless-status` reporting stale evidence after a merge commit is expected until
  `just headless-release-candidate` is run again on the new `HEAD`.
- Hardware/HIL failures are not active blockers for the current headless scope. They remain future
  evidence contracts until real devices are connected and explicitly brought into scope.
