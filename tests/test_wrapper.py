"""Tests for the pseudo-terminal wrapper module."""

import pytest

from runtfy.wrapper import run


@pytest.fixture(autouse=True)
def mock_notifier_send(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure wrapper tests never make external network calls."""
    monkeypatch.setattr("runtfy.notifier.send", lambda *args, **kwargs: True)



def test_echo_success(capfd: pytest.CaptureFixture[str]) -> None:
    """Running ['echo', 'hello'] exits with code 0 and the output contains 'hello'."""
    exit_code = run(["echo", "hello"])
    captured = capfd.readouterr()
    assert exit_code == 0
    assert "hello" in captured.out


def test_exit_code_42() -> None:
    """Running ['sh', '-c', 'exit 42'] exits with code 42."""
    exit_code = run(["sh", "-c", "exit 42"])
    assert exit_code == 42


def test_exit_code_false() -> None:
    """Running ['false'] exits with code 1."""
    exit_code = run(["false"])
    assert exit_code == 1


def test_nonexistent_command(capfd: pytest.CaptureFixture[str]) -> None:
    """Running a command that does not exist exits with non-zero code and does not raise."""
    exit_code = run(["nonexistent_command_xyz_12345"])
    captured = capfd.readouterr()
    assert exit_code != 0
    assert "command not found" in captured.out or "command not found" in captured.err


def test_empty_command() -> None:
    """Running with an empty command list exits with non-zero code without raising."""
    exit_code = run([])
    assert exit_code != 0
