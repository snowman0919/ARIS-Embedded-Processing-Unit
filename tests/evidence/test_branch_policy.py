import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_branch_policy import validate_refs


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
