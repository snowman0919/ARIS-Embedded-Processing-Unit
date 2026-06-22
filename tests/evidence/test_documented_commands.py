import sys
import stat
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_documented_commands import validate, iter_references


def test_current_documented_commands_resolve():
    workspace = Path(__file__).resolve().parents[2]

    assert validate(workspace) == []


def test_documented_scripts_are_executable():
    workspace = Path(__file__).resolve().parents[2]
    scripts = sorted(
        {
            workspace / reference.name
            for reference in iter_references(workspace)
            if reference.kind == "script"
        }
    )

    assert scripts
    non_executable = [
        path.relative_to(workspace).as_posix()
        for path in scripts
        if not path.stat().st_mode & stat.S_IXUSR
    ]
    assert non_executable == []
