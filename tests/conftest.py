"""Run paste_redact.py as a user would, never touching the real terms file."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

SCRIPT = Path(__file__).parents[1] / "paste_redact.py"


class Result(NamedTuple):
    out: str
    err: str
    code: int


class Runner:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.terms_file = tmp_path / "terms.txt"

    def __call__(
        self,
        stdin: str | bytes,
        terms: str | bytes | None = "",
        args: tuple[str, ...] = (),
        env: dict[str, str | None] | None = None,
    ) -> Result:
        """Run the script. `terms=None` leaves the terms file missing."""
        if terms is not None:
            data = terms.encode() if isinstance(terms, str) else terms
            self.terms_file.write_bytes(data)
        wanted: dict[str, str | None] = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.tmp_path),  # never the real home directory
            "PASTE_REDACT_TERMS": str(self.terms_file),
        }
        wanted.update(env or {})  # a None value removes the variable
        environment = {k: v for k, v in wanted.items() if v is not None}
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            input=stdin.encode() if isinstance(stdin, str) else stdin,
            capture_output=True,
            env=environment,
            check=False,
        )
        return Result(proc.stdout.decode(), proc.stderr.decode(), proc.returncode)


@pytest.fixture
def run(tmp_path: Path) -> Runner:
    return Runner(tmp_path)
