"""Tests for the screen locker and input watcher module."""

import sys
from unittest.mock import MagicMock, patch
import pytest

from runtfy.cli import main
from runtfy.locker import (
    CooldownTracker,
    get_hid_idle_time,
    lock_and_watch,
    lock_screen,
    lock_screen_linux,
)


def test_lock_screen_invokes_pmset() -> None:
    """Mocks the lock command call and verifies it is invoked on macOS."""
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = ""

    with patch("subprocess.run", mock_run):
        success, err = lock_screen()

        assert success is True
        assert err == ""
        assert mock_run.call_count == 1
        args, kwargs = mock_run.call_args
        assert args[0] == ["pmset", "displaysleepnow"]
        assert kwargs.get("timeout") == 5.0


def test_cooldown_tracker_enforces_60_seconds() -> None:
    """Verifies the 60-second cooldown prevents a second callback within the window."""
    tracker = CooldownTracker(cooldown_seconds=60.0)

    # Initial event at t = 100.0 triggers
    assert tracker.should_trigger(now=100.0) is True

    # Immediate subsequent events within 60s do NOT trigger
    assert tracker.should_trigger(now=105.0) is False
    assert tracker.should_trigger(now=130.0) is False
    assert tracker.should_trigger(now=159.9) is False

    # Event at exactly 60s after last trigger triggers
    assert tracker.should_trigger(now=160.0) is True

    # Event 10s after second trigger does not trigger
    assert tracker.should_trigger(now=170.0) is False

    # Event 60s after second trigger triggers
    assert tracker.should_trigger(now=220.0) is True


def test_lock_failure_triggers_callback_with_error_and_no_exception() -> None:
    """Verifies that a lock failure triggers the callback with an error message, not an exception."""
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Permission denied: unable to sleep display"
    mock_run.return_value.stdout = ""

    mock_cb = MagicMock()

    with patch("subprocess.run", mock_run):
        # Must not raise an exception
        stop_fn = lock_and_watch(mock_cb, platform="darwin")
        stop_fn()

        # Callback must have been called with the error message
        assert mock_cb.call_count == 1
        kwargs = mock_cb.call_args.kwargs
        args = mock_cb.call_args.args
        error_arg = kwargs.get("error") or (args[0] if args else "")
        assert "Lock command failed" in error_arg or "Permission denied" in error_arg


def test_get_hid_idle_time_parsing() -> None:
    """Test parsing HIDIdleTime from ioreg output."""
    mock_output = '  | |   "HIDIdleTime" = 5432100000\n'
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = mock_output

    with patch("subprocess.run", mock_run):
        idle = get_hid_idle_time()
        assert idle == 5432100000


def test_linux_lock_tries_loginctl_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Linux (mocked sys.platform = 'linux'), verify loginctl lock-session is tried."""
    monkeypatch.setattr(sys, "platform", "linux")
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = ""

    mock_cb = MagicMock()

    with patch("subprocess.run", mock_run):
        stop_fn = lock_and_watch(mock_cb)
        stop_fn()

        assert mock_run.call_count == 1
        assert mock_run.call_args[0][0] == ["loginctl", "lock-session"]
        mock_cb.assert_not_called()


def test_linux_lock_tries_fallbacks_when_first_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify fallback commands are tried if the first fails on Linux."""
    monkeypatch.setattr(sys, "platform", "linux")

    # Call 1: loginctl fails, Call 2: xdg-screensaver succeeds
    res_fail = MagicMock(returncode=1, stderr="loginctl not found", stdout="")
    res_succ = MagicMock(returncode=0, stderr="", stdout="")
    mock_run = MagicMock(side_effect=[res_fail, res_succ])

    mock_cb = MagicMock()

    with patch("subprocess.run", mock_run):
        stop_fn = lock_and_watch(mock_cb)
        stop_fn()

        assert mock_run.call_count == 2
        calls = [call[0][0] for call in mock_run.call_args_list]
        assert calls[0] == ["loginctl", "lock-session"]
        assert calls[1] == ["xdg-screensaver", "lock"]
        mock_cb.assert_not_called()


def test_linux_no_input_watching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify no input-watching callback or thread is registered on Linux."""
    monkeypatch.setattr(sys, "platform", "linux")
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    mock_cb = MagicMock()

    with patch("subprocess.run", mock_run), patch("threading.Thread") as mock_thread:
        stop_fn = lock_and_watch(mock_cb)
        stop_fn()

        # Input watcher thread should NOT be started on Linux
        assert mock_thread.call_count == 0
        mock_cb.assert_not_called()


def test_linux_lock_failure_triggers_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When all Linux lock commands fail, callback is notified and no exception is raised."""
    monkeypatch.setattr(sys, "platform", "linux")
    res_fail = MagicMock(returncode=1, stderr="Lock failed", stdout="")
    mock_run = MagicMock(side_effect=[res_fail, res_fail, res_fail])
    mock_cb = MagicMock()

    with patch("subprocess.run", mock_run):
        stop_fn = lock_and_watch(mock_cb)
        stop_fn()

        assert mock_run.call_count == 3
        assert mock_cb.call_count == 1
        kwargs = mock_cb.call_args.kwargs
        args = mock_cb.call_args.args
        err_msg = kwargs.get("error") or (args[0] if args else "")
        assert "failed" in err_msg


def test_cli_lock_when_away_activates_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """runtfy --lock-when-away activates lock_and_watch and executes command."""
    mock_lock_and_watch = MagicMock(return_value=lambda: None)
    mock_run = MagicMock(return_value=0)

    monkeypatch.setattr("runtfy.cli.lock_and_watch", mock_lock_and_watch)
    monkeypatch.setattr("runtfy.cli.run", mock_run)

    with pytest.raises(SystemExit) as exc:
        main(["--lock-when-away", "echo", "away_mode"])

    assert exc.value.code == 0
    assert mock_lock_and_watch.call_count == 1
    mock_run.assert_called_once_with(["echo", "away_mode"])
