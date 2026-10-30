"""Tests for Claude Code hook handlers (hook-stop and hook-notify)."""

import io
import json
from unittest.mock import patch
import pytest

from runtfy.cli import main
from runtfy.hooks import handle_notify_hook, handle_stop_hook


def test_hook_stop_valid_payload() -> None:
    """hook-stop with a valid payload sends the correct title and message."""
    payload = json.dumps({"final_message": "Build finished successfully"})

    with patch("runtfy.notifier.send") as mock_send:
        handle_stop_hook(stdin_data=payload)

        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "Claude Code finished"
        assert "Session completed." in body


def test_hook_stop_malformed_json_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """hook-stop with malformed JSON does not raise and exits 0."""
    monkeypatch.setattr("sys.stdin", io.StringIO("not valid { json"))

    with patch("runtfy.notifier.send") as mock_send:
        with pytest.raises(SystemExit) as exc_info:
            main(["hook-stop"])

        assert exc_info.value.code == 0
        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "Claude Code finished"
        assert "Session completed." in body


def test_hook_notify_valid_payload() -> None:
    """hook-notify with a valid payload sends a notification with context."""
    payload = json.dumps({"message": "Please approve terminal command execution"})

    with patch("runtfy.notifier.send") as mock_send:
        handle_notify_hook(stdin_data=payload)

        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "Claude Code needs input"
        assert "Please approve terminal command execution" in body


def test_hook_notify_empty_stdin_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """hook-notify with empty stdin does not raise and exits 0."""
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with patch("runtfy.notifier.send") as mock_send:
        with pytest.raises(SystemExit) as exc_info:
            main(["hook-notify"])

        assert exc_info.value.code == 0
        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "Claude Code needs input"
        assert "Claude Code is waiting for permission or input." in body


def test_hook_stop_summary_truncated() -> None:
    """Summary content is truncated to 300 characters when summary = true."""
    long_text = "Z" * 500
    payload = json.dumps({"final_message": long_text})
    cfg = {
        "runtfy": {
            "topic": "test-topic-placeholder",
            "summary": True,
            "summary_lines": 5,
        },
        "quiet_hours": {"enabled": False},
        "events": {"finish": True},
    }

    with patch("runtfy.notifier.send") as mock_send:
        handle_stop_hook(stdin_data=payload, config=cfg)

        assert mock_send.call_count == 1
        title, body = mock_send.call_args[0][:2]
        assert title == "Claude Code finished"
        assert len(body) <= 300
        assert body.endswith("...")


def test_hook_stop_summary_false_omits_message() -> None:
    """When summary = false, final message is omitted from body."""
    payload = json.dumps({"final_message": "Secret or long assistant output"})
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
        handle_stop_hook(stdin_data=payload, config=cfg)

        assert mock_send.call_count == 1
        body = mock_send.call_args[0][1]
        assert "Secret or long assistant output" not in body
        assert "Session completed." in body
