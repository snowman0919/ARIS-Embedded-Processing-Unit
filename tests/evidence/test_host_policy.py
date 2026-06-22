import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_host_policy import validate


def test_current_host_policy_holds():
    workspace = Path(__file__).resolve().parents[2]

    assert validate(workspace) == []
