import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_branch_policy import validate_refs


def test_branch_policy_accepts_named_milestones():
    blockers = validate_refs(
        current_branch="milestone/headless-simulation-embedded",
        local_branches=[
            "main",
            "milestone/teach-repeat-route-replay",
            "milestone/lidar-localization-gazebo",
            "milestone/semantic-hd-map",
            "milestone/goal-based-navigation",
            "milestone/dynamic-obstacle-advisory",
            "milestone/headless-simulation-embedded",
        ],
        remote_branches=[
            "main",
            "milestone/teach-repeat-route-replay",
            "milestone/headless-simulation-embedded",
        ],
    )

    assert blockers == []


def test_branch_policy_rejects_version_and_task_branches():
    blockers = validate_refs(
        current_branch="v6",
        local_branches=["main", "v6", "codex/v2-gazebo-moving-localization"],
        remote_branches=["main", "v1", "codex/v3-map"],
    )

    assert "current branch is not an ARIS milestone branch: v6" in blockers
    assert "unexpected local branch: codex/v2-gazebo-moving-localization" in blockers
    assert "unexpected local branch: v6" in blockers
    assert "unexpected origin branch: codex/v3-map" in blockers
    assert "unexpected origin branch: v1" in blockers
