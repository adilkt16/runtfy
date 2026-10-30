"""Tests for the runtfy CLI entry point."""

import shutil
import subprocess
import sys

CMD = ["runtfy"] if shutil.which("runtfy") else [sys.executable, "-m", "runtfy.cli"]


def test_cli_echo_hello() -> None:
    """runtfy echo hello (via subprocess) exits 0."""
    result = subprocess.run([*CMD, "echo", "hello"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_cli_exit_code_7() -> None:
    """runtfy sh -c 'exit 7' (via subprocess) exits 7."""
    result = subprocess.run([*CMD, "sh", "-c", "exit 7"], capture_output=True, text=True)
    assert result.returncode == 7


def test_cli_no_args() -> None:
    """runtfy with no arguments exits 1 and shows usage."""
    result = subprocess.run(CMD, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Usage:" in result.stderr
