import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_bootstrap_doctor import generate_report


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "docker").mkdir(parents=True)
    (workspace / "docs").mkdir()
    (workspace / "scripts").mkdir()
    for relative in (
        "README.md",
        "flake.nix",
        "justfile",
        "docs/environment.md",
        "docs/verification_plan.md",
        "docker/compose.yaml",
        "docker/ros2.Dockerfile",
        "docker/embedded.Dockerfile",
    ):
        (workspace / relative).write_text("{}\n", encoding="utf-8")
    (workspace / ".env.example").write_text(
        "NGC_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:<choose-current-arm64-dgx-spark-compatible-tag>\n"
        "ARIS_ENABLE_REAL_ACTUATION=0\n",
        encoding="utf-8",
    )
    for relative in (
        "scripts/check_host.sh",
        "scripts/check_bootstrap_doctor.sh",
        "scripts/docker_build.sh",
        "scripts/check_branch_policy.sh",
        "scripts/check_headless_status.sh",
        "scripts/check_headless_release_candidate.sh",
        "scripts/check_embedded_dry_run.sh",
        "scripts/check_documented_commands.sh",
        "scripts/check_architecture_contracts.sh",
        "scripts/check_host_policy.sh",
        "scripts/check_core_readiness.sh",
        "scripts/check_python_tests.sh",
        "scripts/check_mcu_serial_loopback.sh",
        "scripts/check_scan_cloud_contract.sh",
        "scripts/check_operator_goal.sh",
        "scripts/check_v3_semantic_map.sh",
        "scripts/check_v6_semantic_review.sh",
        "scripts/check_v4_goal_nav.sh",
        "scripts/check_v5_dynamic_obstacle.sh",
        "scripts/check_v2_gazebo_stack.sh",
        "scripts/check_v2_gazebo_lidar.sh",
        "scripts/check_v2_gazebo_localization.sh",
        "scripts/check_v2_gazebo_moving_localization.sh",
        "scripts/check_v2_gazebo_physics.sh",
        "scripts/check_v2_gazebo_physics_localization.sh",
        "scripts/check_v2_gazebo_drift_recovery.sh",
        "scripts/check_core_pipeline_flow.sh",
        "scripts/check_core_pipeline_repeatability.sh",
        "scripts/generate_readiness_evidence_index.py",
        "scripts/generate_operational_readiness_audit.py",
        "scripts/summarize_core_pipeline_repeatability.py",
        "scripts/summarize_headless_status.py",
        "scripts/validate_headless_release_candidate.py",
        "scripts/run_core_readiness_report.sh",
        "scripts/check_headless_readiness_audit.sh",
        "scripts/check_operational_readiness_audit.sh",
    ):
        path = workspace / relative
        path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        path.chmod(0o755)
    return workspace


def _env(workspace: Path, tmp_path: Path) -> dict[str, str]:
    aris_home = tmp_path / "aris"
    data = aris_home / "data"
    logs = aris_home / "logs"
    models = aris_home / "models"
    for path in (data, logs, models):
        path.mkdir(parents=True)
    return {
        **os.environ,
        "ARIS_HOME": str(aris_home),
        "ARIS_WS": str(workspace),
        "ARIS_DATA": str(data),
        "ARIS_LOGS": str(logs),
        "ARIS_MODELS": str(models),
        "ROS_DOMAIN_ID": "42",
        "ROS_LOCALHOST_ONLY": "1",
        "RMW_IMPLEMENTATION": "rmw_fastrtps_cpp",
        "ARIS_ENABLE_REAL_ACTUATION": "0",
    }


def test_bootstrap_doctor_accepts_valid_workspace(tmp_path):
    workspace = _workspace(tmp_path)

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is True
    assert report["blockers"] == []
    assert report["checks"]["safety"]["real_actuation_disabled"] is True


def test_bootstrap_doctor_rejects_real_actuation_enabled(tmp_path):
    workspace = _workspace(tmp_path)
    env = _env(workspace, tmp_path)
    env["ARIS_ENABLE_REAL_ACTUATION"] = "1"

    report = generate_report(workspace, env)

    assert report["valid"] is False
    assert any("ARIS_ENABLE_REAL_ACTUATION" in blocker for blocker in report["blockers"])


def test_bootstrap_doctor_rejects_workspace_mismatch(tmp_path):
    workspace = _workspace(tmp_path)
    env = _env(workspace, tmp_path)
    env["ARIS_WS"] = str(tmp_path / "other")

    report = generate_report(workspace, env)

    assert report["valid"] is False
    assert any("ARIS_WS does not match workspace" in blocker for blocker in report["blockers"])


def test_bootstrap_doctor_requires_branch_policy_entrypoint(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "scripts/check_branch_policy.sh").unlink()

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert "missing required file: scripts/check_branch_policy.sh" in report["blockers"]


def test_bootstrap_doctor_requires_reproducibility_docs(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "docs/environment.md").unlink()

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert "missing required file: docs/environment.md" in report["blockers"]


def test_bootstrap_doctor_requires_release_gate_fallback_entrypoints(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "scripts/check_headless_readiness_audit.sh").unlink()

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert "missing required file: scripts/check_headless_readiness_audit.sh" in report["blockers"]


def test_bootstrap_doctor_requires_release_report_helpers(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "scripts/validate_headless_release_candidate.py").unlink()

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert "missing required file: scripts/validate_headless_release_candidate.py" in report["blockers"]


def test_bootstrap_doctor_requires_operational_audit_entrypoint(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "scripts/check_operational_readiness_audit.sh").unlink()

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert "missing required file: scripts/check_operational_readiness_audit.sh" in report["blockers"]


def test_bootstrap_doctor_requires_core_readiness_child_entrypoints(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "scripts/check_v2_gazebo_physics_localization.sh").unlink()

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert (
        "missing required file: scripts/check_v2_gazebo_physics_localization.sh"
        in report["blockers"]
    )


def test_bootstrap_doctor_requires_fallback_scripts_executable(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "scripts/check_core_pipeline_repeatability.sh").chmod(0o644)

    report = generate_report(workspace, _env(workspace, tmp_path))

    assert report["valid"] is False
    assert (
        "required script is not executable: scripts/check_core_pipeline_repeatability.sh"
        in report["blockers"]
    )
