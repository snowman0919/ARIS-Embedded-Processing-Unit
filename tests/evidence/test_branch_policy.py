import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_branch_policy import generate_report, validate_refs


def test_branch_policy_accepts_version_context_branches():
    blockers = validate_refs(
        current_branch="v6-headless-simulation-embedded",
        local_branches=[
            "main",
            "v1-teach-repeat-route-replay",
            "v2-lidar-localization-gazebo",
            "v3-semantic-hd-map",
            "v4-goal-based-navigation",
            "v5-dynamic-obstacle-advisory",
            "v6-headless-simulation-embedded",
        ],
        remote_branches=[
            "main",
            "v1-teach-repeat-route-replay",
            "v6-headless-simulation-embedded",
        ],
    )

    assert blockers == []


def test_branch_policy_rejects_version_and_task_branches():
    blockers = validate_refs(
        current_branch="milestone/headless-simulation-embedded",
        local_branches=["main", "milestone/headless-simulation-embedded", "codex/v2-gazebo-moving-localization"],
        remote_branches=["main", "v6", "codex/v3-map"],
    )

    assert (
        "current branch is not an ARIS vN-context branch: milestone/headless-simulation-embedded"
        in blockers
    )
    assert "unexpected local branch: codex/v2-gazebo-moving-localization" in blockers
    assert "unexpected local branch: milestone/headless-simulation-embedded" in blockers
    assert "unexpected origin branch: codex/v3-map" in blockers
    assert "unexpected origin branch: v6" in blockers


def test_branch_policy_report_includes_main_sync(tmp_path, monkeypatch):
    def fake_current_branch(workspace):
        return "v6-headless-simulation-embedded"

    def fake_branch_refs(workspace):
        return (
            ["main", "v6-headless-simulation-embedded"],
            ["main", "v6-headless-simulation-embedded"],
        )

    def fake_main_sync(workspace):
        return {
            "base": "origin/main",
            "head": "origin/v6-headless-simulation-embedded",
            "available": True,
            "main_ahead": 1,
            "v6_ahead": 1,
            "main_contains_v6": False,
        }

    monkeypatch.setattr("check_branch_policy._current_branch", fake_current_branch)
    monkeypatch.setattr("check_branch_policy._branch_refs", fake_branch_refs)
    monkeypatch.setattr("check_branch_policy._main_sync", fake_main_sync)

    report = generate_report(tmp_path)

    assert report["valid"] is True
    assert report["main_sync"] == {
        "base": "origin/main",
        "head": "origin/v6-headless-simulation-embedded",
        "available": True,
        "main_ahead": 1,
        "v6_ahead": 1,
        "main_contains_v6": False,
    }
