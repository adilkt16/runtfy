"""ntfy notification delivery module."""

from __future__ import annotations

import datetime
from email.header import Header
import socket
import sys
from typing import Any
import urllib.error
import urllib.request

from runtfy.config import load_config


def _encode_header(val: str) -> str:
    """Safely encode HTTP header string, using RFC 2047 if non-ASCII."""
    try:
        val.encode("ascii")
        return val
    except UnicodeEncodeError:
        return Header(val, "utf-8").encode()


def is_in_quiet_hours(
    start_str: str,
    end_str: str,
    current_time: datetime.time | None = None,
) -> bool:
    """Check if current_time (defaulting to now) falls within the [start, end] window."""
    if current_time is None:
        current_time = datetime.datetime.now().time()

    try:
        start = datetime.time.fromisoformat(start_str)
        end = datetime.time.fromisoformat(end_str)
    except ValueError:
        return False

    if start <= end:
        return start <= current_time <= end
    # Window spans midnight (e.g. 22:00 to 08:00)
    return current_time >= start or current_time <= end


def _log_delivery_failure(err: Exception, topic: str = "") -> None:
    """Log a notification delivery failure without ever including the ntfy topic."""
    if isinstance(err, (TimeoutError, socket.timeout)):
        detail = "timeout"
    elif isinstance(err, urllib.error.HTTPError):
        detail = f"HTTP {err.code}"
    elif isinstance(err, urllib.error.URLError):
        detail = "connection error"
    else:
        detail = type(err).__name__

    msg = f"runtfy: notification delivery failed ({detail})\n"
    if topic:
        msg = msg.replace(topic, "<redacted>")
    sys.stderr.write(msg)


def send_notification(
    title: str,
    body: str,
    event: str = "finish",
    config: dict[str, Any] | None = None,
    current_time: datetime.time | None = None,
) -> bool:
    """Send a notification via ntfy HTTP POST.

    Args:
        title: Notification title string.
        body: Notification body text.
        event: Event type ('finish', 'waiting', etc.).
        config: Optional configuration dictionary. Defaults to loaded config.
        current_time: Optional time override for quiet hours evaluation.

    Returns:
        True if the notification was successfully sent, False if skipped or failed.
    """
    cfg = config if config is not None else load_config()

    # Check event toggles
    events = cfg.get("events", {})
    if event in events and not events[event]:
        return False

    # Check quiet hours
    quiet = cfg.get("quiet_hours", {})
    if quiet.get("enabled", False):
        start_str = quiet.get("start", "22:00")
        end_str = quiet.get("end", "08:00")
        if is_in_quiet_hours(start_str, end_str, current_time=current_time):
            return False

    runtfy_cfg = cfg.get("runtfy", {})
    topic = runtfy_cfg.get("topic", "").strip()
    if not topic:
        return False

    server = runtfy_cfg.get("server", "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"

    req = urllib.request.Request(
        url=url,
        data=body.encode("utf-8"),
        headers={"Title": _encode_header(title)},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        _log_delivery_failure(e, topic)
        return False


# Convenient aliases
notify = send_notification
send = send_notification


def send_input_alert(config: dict[str, Any] | None = None) -> bool:
    """Send an alert when input is detected while the screen was locked."""
    title = "runtfy: input detected"
    body = "Someone typed or moved the mouse while your screen was locked."
    return send_notification(title, body, event="waiting", config=config)


def send_lock_failed_alert(error_detail: str = "", config: dict[str, Any] | None = None) -> bool:
    """Send an alert if screen locking fails (FR12)."""
    title = "runtfy: screen lock failed"
    body = (
        f"Screen lock failed: {error_detail}. The command is running but your screen remains unlocked."
        if error_detail
        else "Screen lock failed. The command is running but your screen remains unlocked."
    )
    return send_notification(title, body, event="waiting", config=config)


