"""Screen locking and input watching module for macOS and Linux (FR7, FR8, FR12)."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from typing import Any, Callable

LINUX_LOCK_COMMANDS: list[list[str]] = [
    ["loginctl", "lock-session"],
    ["xdg-screensaver", "lock"],
    ["gnome-screensaver-command", "--lock"],
]


class CooldownTracker:
    """Track event triggers and enforce cooldown intervals (FR8)."""

    def __init__(self, cooldown_seconds: float = 60.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.last_triggered: float = -cooldown_seconds

    def should_trigger(self, now: float | None = None) -> bool:
        """Return True if cooldown has elapsed since last trigger."""
        current = time.monotonic() if now is None else now
        if current - self.last_triggered >= self.cooldown_seconds:
            self.last_triggered = current
            return True
        return False


def lock_screen(lock_cmd: list[str] | None = None) -> tuple[bool, str]:
    """Lock the display on macOS using native pmset command.

    Choice of lock command:
    We use `pmset displaysleepnow` rather than AppleScript keystrokes because:
    1. It requires zero Accessibility or Automation (TCC) permissions.
    2. AppleScript (`osascript`) keystrokes fail if Terminal/Python has not been
       explicitly granted Accessibility privileges in System Settings.
    3. `pmset displaysleepnow` works natively and reliably across macOS versions.

    Returns:
        tuple (success, error_message)
    """
    cmd = lock_cmd if lock_cmd is not None else ["pmset", "displaysleepnow"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
        if res.returncode == 0:
            return True, ""
        err = res.stderr.strip() or f"exit code {res.returncode}"
        return False, f"Lock command failed: {err}"
    except Exception as e:
        return False, f"Lock execution error: {e}"


def lock_screen_linux(commands: list[list[str]] | None = None) -> tuple[bool, str]:
    """Attempt to lock the screen on Linux, trying commands in order until one succeeds.

    Commands tried in order:
    1. loginctl lock-session (standard on modern systemd/logind Linux desktops)
    2. xdg-screensaver lock (freedesktop.org standard)
    3. gnome-screensaver-command --lock (GNOME-specific fallback)

    Returns:
        tuple (success, error_message)
    """
    cmds = commands if commands is not None else LINUX_LOCK_COMMANDS
    last_error = "No lock commands available"
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                return True, ""
            err = res.stderr.strip() or f"exit code {res.returncode}"
            last_error = f"{cmd[0]} failed: {err}"
        except Exception as e:
            last_error = f"{cmd[0]} failed: {e}"
    return False, last_error


def get_hid_idle_time(cmd: list[str] | None = None) -> int | None:
    """Read HIDIdleTime in nanoseconds from ioreg.

    Trade-offs: `ioreg` vs `CGEventTap`:
    - `CGEventTap` requires C bindings and explicitly requires user-granted
      "Input Monitoring" or "Accessibility" permissions. Without them, it fails
      silently or returns NULL.
    - `ioreg -c IOHIDSystem` reads the kernel HID idle counter with standard user
      privileges, zero extra permissions, and no external C/PyObjC dependencies.
    Hence, `ioreg` is the most reliable and lightweight approach.
    """
    command = cmd if cmd is not None else ["ioreg", "-c", "IOHIDSystem"]
    try:
        res = subprocess.run(command, capture_output=True, text=True, timeout=2.0)
        if res.returncode == 0:
            match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', res.stdout)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return None


def _invoke_callback(callback: Callable[..., Any], error: str | None = None) -> None:
    """Safely invoke callback with optional error message."""
    try:
        if error:
            try:
                callback(error=error)
            except TypeError:
                try:
                    callback(error)
                except TypeError:
                    callback()
        else:
            callback()
    except Exception:
        pass


def lock_and_watch(
    callback: Callable[..., Any],
    platform: str | None = None,
    lock_cmd: list[str] | None = None,
    cooldown_seconds: float = 60.0,
    poll_interval: float = 1.0,
    idle_time_fn: Callable[[], int | None] | None = None,
) -> Callable[[], None]:
    """Lock the screen and optionally watch for input while locked.

    Platform behavior:
    - macOS ('darwin'): Locks screen via pmset, starts input watcher with 60s cooldown.
    - Linux ('linux'): Locks screen via loginctl/xdg-screensaver/gnome-screensaver.
      Input watching is NOT performed on Linux (v0.1 non-goal).
    - If locking fails on either platform, alerts callback with error and continues (FR12).

    Args:
        callback: Function called on input detection (macOS), or with error keyword on lock failure.
        platform: Platform override (defaults to sys.platform).
        lock_cmd: Optional lock command override for testing.
        cooldown_seconds: Minimum seconds between consecutive input alerts (macOS, default 60s).
        poll_interval: Seconds between ioreg polling checks (macOS).
        idle_time_fn: Custom function returning HIDIdleTime nanoseconds (macOS).

    Returns:
        A callable stop() function to terminate any active watcher.
    """
    target_platform = platform if platform is not None else sys.platform

    if target_platform.startswith("linux"):
        # Linux path: lock screen using first working command, no input watching
        cmds = [lock_cmd] if lock_cmd is not None else LINUX_LOCK_COMMANDS
        success, err_msg = lock_screen_linux(commands=cmds)
        if not success:
            sys.stderr.write(f"runtfy: screen lock failed: {err_msg}\n")
            _invoke_callback(callback, error=err_msg)
        return lambda: None

    # macOS path (darwin): lock screen and watch input
    success, err_msg = lock_screen(lock_cmd=lock_cmd)
    if not success:
        _invoke_callback(callback, error=err_msg)

    stop_event = threading.Event()
    tracker = CooldownTracker(cooldown_seconds=cooldown_seconds)
    get_idle = idle_time_fn if idle_time_fn is not None else get_hid_idle_time

    def _watcher_loop() -> None:
        if stop_event.wait(timeout=2.0):
            return

        last_idle = get_idle()

        while not stop_event.is_set():
            if stop_event.wait(timeout=poll_interval):
                break

            current_idle = get_idle()
            if current_idle is not None:
                if last_idle is not None and (current_idle < last_idle or current_idle < 1_000_000_000):
                    if tracker.should_trigger():
                        _invoke_callback(callback)
                last_idle = current_idle

    thread = threading.Thread(target=_watcher_loop, daemon=True, name="runtfy-locker-watcher")
    thread.start()

    def stop() -> None:
        stop_event.set()

    return stop
