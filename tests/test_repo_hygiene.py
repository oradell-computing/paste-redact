"""The script's shebang only works if git records it as executable.

Ruff's EXE001 check catches a missing executable bit, but ruff skips that check on some
platforms (WSL is one), so this test checks the mode git actually stores.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_the_script_is_executable_in_git() -> None:
    entry = subprocess.run(
        ["git", "ls-files", "-s", "paste_redact.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert entry.split()[0] == "100755"
