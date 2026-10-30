"""Claude Code hook installer and manager."""

from __future__ import annotations

import datetime
import difflib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Callable

from runtfy.config import load_config
from runtfy import notifier


def get_claude_settings_path() -> Path:
    """Return the path to the Claude Code settings file (~/.claude/settings.json)."""
    return Path.home() / ".claude" / "settings.json"


def _has_hook_command(hook_entries: list[Any], command: str) -> bool:
    """Check if any hook in the list already contains the given command."""
    for entry in hook_entries:
        if isinstance(entry, dict):
            if entry.get("command") == command:
                return True
            for nested in entry.get("hooks", []):
                if isinstance(nested, dict) and nested.get("command") == command:
                    return True
    return False


def _build_hook_entry(command: str) -> dict[str, Any]:
    """Construct standard Claude Code hook structure."""
    return {
        "hooks": [
            {
                "type": "command",
                "command": command,
            }
        ]
    }


def update_settings_hooks(settings: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Add runtfy Stop and Notification hooks to settings if not already present.

    Returns:
        tuple (updated_settings, changed)
    """
    updated = json.loads(json.dumps(settings))
    hooks = updated.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        updated["hooks"] = hooks

    changed = False

    # Stop hook: runs after every Claude Code session ends
    stop_list = hooks.setdefault("Stop", [])
    if not isinstance(stop_list, list):
        stop_list = []
        hooks["Stop"] = stop_list
    if not _has_hook_command(stop_list, "runtfy hook-stop"):
        stop_list.append(_build_hook_entry("runtfy hook-stop"))
        changed = True

    # Notification hook: runs when Claude Code needs input
    notify_list = hooks.setdefault("Notification", [])
    if not isinstance(notify_list, list):
        notify_list = []
        hooks["Notification"] = notify_list
    if not _has_hook_command(notify_list, "runtfy hook-notify"):
        notify_list.append(_build_hook_entry("runtfy hook-notify"))
        changed = True

    return updated, changed


def install_hooks(
    settings_path: Path | None = None,
    prompt_fn: Callable[[str], str] | None = None,
) -> bool:
    """Install runtfy hooks into Claude Code settings.

    Shows diff, asks for confirmation, creates a timestamped backup, and writes updated JSON.

    Args:
        settings_path: Optional path to settings.json (defaults to ~/.claude/settings.json).
        prompt_fn: Optional input prompt function.

    Returns:
        True if hooks were installed or already installed, False if aborted.
    """
    target = settings_path if settings_path is not None else get_claude_settings_path()

    orig_text = ""
    settings: dict[str, Any] = {}
    if target.is_file():
        try:
            orig_text = target.read_text(encoding="utf-8")
            settings = json.loads(orig_text) if orig_text.strip() else {}
        except Exception:
            settings = {}
    else:
        settings = {}

    updated_settings, changed = update_settings_hooks(settings)
    new_text = json.dumps(updated_settings, indent=2) + "\n"

    if not changed:
        print("Hooks already installed.")
        return True

    # Generate unified diff
    diff_lines = list(
        difflib.unified_diff(
            orig_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(target) if orig_text else "/dev/null",
            tofile=str(target),
        )
    )

    if diff_lines:
        sys.stdout.write("".join(diff_lines))
        sys.stdout.flush()

    ask = prompt_fn if prompt_fn is not None else input
    try:
        answer = ask("Proceed? [y/N]: ")
    except (EOFError, OSError):
        answer = "n"

    if answer.strip().lower() not in ("y", "yes"):
        print("Aborted.")
        return False

    # Create timestamped backup of the original file if it existed
    if target.is_file():
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = target.parent / f"{target.name}.{timestamp}.bak"
        shutil.copy2(target, backup_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8")

    print("Hooks installed. Run runtfy init if you haven't already.")
    return True


def extract_final_message(payload: Any) -> str:
    """Extract assistant message from Claude Code hook JSON payload."""
    if not isinstance(payload, dict):
        return ""

    for key in ("final_message", "message", "last_message", "response", "content"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    for list_key in ("messages", "transcript", "history"):
        entries = payload.get(list_key)
        if isinstance(entries, list) and entries:
            for item in reversed(entries):
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if isinstance(content, list):
                        parts = [b.get("text", "") for b in content if isinstance(b, dict)]
                        joined = " ".join(filter(None, parts)).strip()
                        if joined:
                            return joined
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
    return ""


def handle_stop_hook(
    stdin_data: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Handle Claude Code Stop hook notification (FR4).

    Parses JSON payload from stdin, extracts final message if available,
    and sends a notification with title 'Claude Code finished'.
    """
    title = "Claude Code finished"
    body = "Session completed."
    cfg = config if config is not None else load_config()

    try:
        raw = stdin_data if stdin_data is not None else sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        final_msg = extract_final_message(payload)

        runtfy_cfg = cfg.get("runtfy", {})
        if runtfy_cfg.get("summary", False) and final_msg:
            truncated_msg = final_msg if len(final_msg) <= 300 else final_msg[:297] + "..."
            body = f"{body}\n\n{truncated_msg}"
            if len(body) > 300:
                body = body[:297] + "..."
    except Exception:
        pass

    try:
        notifier.send(title, body, event="finish", config=cfg)
    except Exception:
        pass


def extract_notification_context(payload: Any) -> str:
    """Extract brief context from Claude Code Notification hook payload."""
    if not isinstance(payload, dict):
        return ""

    for key in ("message", "prompt", "text", "context", "title", "notification_type", "type"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def handle_notify_hook(
    stdin_data: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Handle Claude Code Notification hook (FR5).

    Parses JSON payload from stdin and sends a notification with title 'Claude Code needs input'.
    """
    title = "Claude Code needs input"
    body = "Claude Code is waiting for permission or input."
    cfg = config if config is not None else load_config()

    try:
        raw = stdin_data if stdin_data is not None else sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        context = extract_notification_context(payload)
        if context:
            body = f"Waiting for input: {context}"
            if len(body) > 300:
                body = body[:297] + "..."
    except Exception:
        pass

    try:
        notifier.send(title, body, event="waiting", config=cfg)
    except Exception:
        pass
