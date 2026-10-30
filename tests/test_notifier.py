"""Tests for the ntfy notification sender module."""

from datetime import time
from typing import Any
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request
import pytest

from runtfy.notifier import send_notification


@pytest.fixture
def base_config() -> dict[str, Any]:
    return {
        "runtfy": {
            "topic": "test-secret-topic-987",
            "server": "https://ntfy.sh",
            "summary": False,
            "summary_lines": 5,
        },
        "quiet_hours": {
            "enabled": False,
            "start": "22:00",
            "end": "08:00",
        },
        "events": {
            "finish": True,
            "waiting": True,
        },
    }


def test_send_notification_calls_correct_url(base_config: dict[str, Any]) -> None:
    """Sending a notification calls the correct URL with Title header and body."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        success = send_notification(
            title="Task Completed",
            body="Command finished with exit code 0",
            event="finish",
            config=base_config,
        )

        assert success is True
        assert mock_urlopen.call_count == 1

        call_args, call_kwargs = mock_urlopen.call_args
        req = call_args[0]
        assert isinstance(req, urllib.request.Request)
        assert req.full_url == "https://ntfy.sh/test-secret-topic-987"
        assert req.data == b"Command finished with exit code 0"
        assert req.headers.get("Title") == "Task Completed"
        assert call_kwargs.get("timeout") == 5.0


def test_send_notification_custom_server(base_config: dict[str, Any]) -> None:
    """Sending a notification respects a custom user-configured ntfy server."""
    base_config["runtfy"]["server"] = "https://custom-ntfy.example.org/"
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        success = send_notification(
            title="Title",
            body="Body",
            config=base_config,
        )

        assert success is True
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://custom-ntfy.example.org/test-secret-topic-987"


def test_timeout_caught_and_does_not_raise(
    base_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A timeout or connection error is caught, does not raise, and logs a warning."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        success = send_notification(
            title="Title",
            body="Body",
            config=base_config,
        )

        assert success is False
        captured = capsys.readouterr()
        assert "runtfy: notification delivery failed" in captured.err


def test_connection_error_caught_and_does_not_raise(
    base_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A URLError is caught without raising an unhandled exception."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        success = send_notification(
            title="Title",
            body="Body",
            config=base_config,
        )

        assert success is False
        captured = capsys.readouterr()
        assert "runtfy: notification delivery failed" in captured.err


def test_quiet_hours_suppresses_send(base_config: dict[str, Any]) -> None:
    """Quiet-hours logic suppresses sending when current time is inside the quiet window."""
    base_config["quiet_hours"]["enabled"] = True
    base_config["quiet_hours"]["start"] = "22:00"
    base_config["quiet_hours"]["end"] = "08:00"

    with patch("urllib.request.urlopen") as mock_urlopen:
        # Inside quiet window (23:30)
        sent_night = send_notification(
            title="Title",
            body="Body",
            config=base_config,
            current_time=time(23, 30),
        )
        assert sent_night is False
        mock_urlopen.assert_not_called()

        # Inside quiet window (05:00)
        sent_early = send_notification(
            title="Title",
            body="Body",
            config=base_config,
            current_time=time(5, 0),
        )
        assert sent_early is False
        mock_urlopen.assert_not_called()

        # Outside quiet window (14:00)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        sent_day = send_notification(
            title="Title",
            body="Body",
            config=base_config,
            current_time=time(14, 0),
        )
        assert sent_day is True
        mock_urlopen.assert_called_once()


def test_topic_never_present_in_log_or_stderr(
    base_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Topic is never present in any log/stderr output on failure."""
    secret_topic = base_config["runtfy"]["topic"]
    leak_error = urllib.error.URLError(f"Failed to connect to https://ntfy.sh/{secret_topic}")

    with patch("urllib.request.urlopen", side_effect=leak_error):
        success = send_notification(
            title="Title",
            body="Body",
            config=base_config,
        )

        assert success is False
        captured = capsys.readouterr()
        assert secret_topic not in captured.err
        assert secret_topic not in captured.out
        assert "runtfy: notification delivery failed" in captured.err


def test_event_toggles_suppress_send(base_config: dict[str, Any]) -> None:
    """Event toggles disable sending for disabled events."""
    base_config["events"]["finish"] = False
    base_config["events"]["waiting"] = True

    with patch("urllib.request.urlopen") as mock_urlopen:
        sent_finish = send_notification("Title", "Body", event="finish", config=base_config)
        assert sent_finish is False
        mock_urlopen.assert_not_called()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        sent_waiting = send_notification("Title", "Body", event="waiting", config=base_config)
        assert sent_waiting is True
        mock_urlopen.assert_called_once()


def test_missing_topic_skips_send(base_config: dict[str, Any]) -> None:
    """Empty or unconfigured topic skips sending silently."""
    base_config["runtfy"]["topic"] = ""
    with patch("urllib.request.urlopen") as mock_urlopen:
        sent = send_notification("Title", "Body", config=base_config)
        assert sent is False
        mock_urlopen.assert_not_called()
