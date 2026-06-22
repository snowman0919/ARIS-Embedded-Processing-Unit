import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_documented_commands import validate


def test_current_documented_commands_resolve():
    workspace = Path(__file__).resolve().parents[2]

    assert validate(workspace) == []
