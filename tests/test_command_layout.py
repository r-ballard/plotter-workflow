"""Operator commands remain executable from the repository root after relocation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    "dpx3300_convert.py",
    "job_preflight.py",
    "send_hpgl.py",
    "booklet_impose.py",
    "cootie_impose.py",
)


@pytest.mark.parametrize("filename", COMMANDS)
def test_operator_command_runs_from_scripts_directory(filename: str) -> None:
    script = ROOT / "scripts" / filename
    assert script.is_file()
    assert not (ROOT / filename).exists()
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
