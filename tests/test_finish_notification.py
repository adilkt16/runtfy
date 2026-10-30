"""Tests for the finish notification integration in runtfy."""

import re
from unittest.mock import patch
import pytest

from runtfy.wrapper import format_duration, run, send_finish_notification


def test_format_duration() -> None:
    """format_duration converts seconds into human-readable strings."""
    assert format_duration(0.0) == "0s"
    assert format_duration(4.2) == "4s"
    assert format_duration(60.0) == "1m 0s"
    assert format_duration(154.0) == "2m 34s"
    assert format_duration(3665.0) == "1h 1m 5s"


def test_finish_notification_success() -> None:
    """After wrapping echo hello (exit 0), notification has correct title and contains success."""
    with patch("runtfy.notifier.send") as mock_send:
        exit_code = run(["echo", "hello"])

        assert exit_code == 0
        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "runtfy: echo finished"
        assert "Status: ✓ success" in body
        assert "success" in body


def test_finish_notification_failure() -> None:
    """After wrapping sh -c 'exit 1' (exit 1), the body contains failed."""
    with patch("runtfy.notifier.send") as mock_send:
        exit_code = run(["sh", "-c", "exit 1"])

        assert exit_code == 1
        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "runtfy: sh finished"
        assert "Status: ✗ failed (code 1)" in body
        assert "failed" in body


def test_finish_notification_duration_present_and_nonempty() -> None:
    """Duration is present in the notification body and is non-empty."""
    with patch("runtfy.notifier.send") as mock_send:
        run(["echo", "quick"])

        assert mock_send.call_count == 1
        body = mock_send.call_args[0][1]
        match = re.search(r"Duration:\s*(\S+)", body)
        assert match is not None
        duration_value = match.group(1)
        assert len(duration_value) > 0


def test_finish_notification_summary_false() -> None:
    """When summary = false, stdout lines are not in the body."""
    cfg = {
        "runtfy": {
            "topic": "test-topic-placeholder",
            "summary": False,
            "summary_lines": 5,
        },
        "quiet_hours": {"enabled": False},
        "events": {"finish": True},
    }
    with patch("runtfy.notifier.send") as mock_send:
        run(["sh", "-c", "echo line_one; echo line_two; echo line_three"], config=cfg)

        assert mock_send.call_count == 1
        body = mock_send.call_args[0][1]
        assert "line_one" not in body
        assert "line_two" not in body
        assert "line_three" not in body


def test_finish_notification_summary_true() -> None:
    """When summary = true, the last N lines appear in the body."""
    cfg = {
        "runtfy": {
            "topic": "test-topic-placeholder",
            "summary": True,
            "summary_lines": 2,
        },
        "quiet_hours": {"enabled": False},
        "events": {"finish": True},
    }
    with patch("runtfy.notifier.send") as mock_send:
        run(["sh", "-c", "echo alpha; echo beta; echo gamma"], config=cfg)

        assert mock_send.call_count == 1
        body = mock_send.call_args[0][1]
        assert "alpha" not in body
        assert "beta" in body
        assert "gamma" in body


def test_finish_notification_summary_truncated() -> None:
    """Summary text is truncated so total body is at most 300 characters."""
    cfg = {
        "runtfy": {
            "topic": "test-topic-placeholder",
            "summary": True,
            "summary_lines": 10,
        },
        "quiet_hours": {"enabled": False},
        "events": {"finish": True},
    }
    with patch("runtfy.notifier.send") as mock_send:
        run(["sh", "-c", "python3 -c 'print(\"A\" * 400)'"], config=cfg)

        assert mock_send.call_count == 1
        body = mock_send.call_args[0][1]
        assert len(body) <= 300
        assert body.endswith("...")


def test_notifier_failure_does_not_change_exit_code() -> None:
    """Notifier failure (mocked to raise) does not change exit code or block wrapper."""
    with patch("runtfy.notifier.send", side_effect=RuntimeError("Connection exploded")):
        exit_code = run(["sh", "-c", "exit 42"])
        assert exit_code == 42
