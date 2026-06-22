import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_bootstrap_doctor import generate_report


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "docker").mkdir(parents=True)
    (workspace / "scripts").mkdir()
    for relative in (
        "flake.nix",
        "justfile",
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
    for relative in ("scripts/check_host.sh", "scripts/check_headless_release_candidate.sh"):
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
