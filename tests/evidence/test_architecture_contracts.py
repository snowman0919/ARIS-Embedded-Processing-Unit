import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_architecture_contracts import validate


def test_current_architecture_contracts_hold():
    workspace = Path(__file__).resolve().parents[2]

    assert validate(workspace) == []
