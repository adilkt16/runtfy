"""Configuration management and runtfy init subcommand logic."""

from __future__ import annotations

import os
from pathlib import Path
import secrets
from typing import Any, Callable

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_CONFIG: dict[str, Any] = {
    "runtfy": {
        "topic": "",
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


def get_config_path() -> Path:
    """Return the default configuration file path (~/.config/runtfy/config.toml)."""
    return Path.home() / ".config" / "runtfy" / "config.toml"


def merge_defaults(loaded: dict[str, Any] | None) -> dict[str, Any]:
    """Merge loaded configuration data with defaults to ensure all keys are present."""
    merged: dict[str, Any] = {
        "runtfy": dict(DEFAULT_CONFIG["runtfy"]),
        "quiet_hours": dict(DEFAULT_CONFIG["quiet_hours"]),
        "events": dict(DEFAULT_CONFIG["events"]),
    }
    if not isinstance(loaded, dict):
        return merged

    for section, section_defaults in DEFAULT_CONFIG.items():
        sec_data = loaded.get(section)
        if isinstance(sec_data, dict):
            for key in section_defaults:
                if key in sec_data:
                    merged[section][key] = sec_data[key]

    return merged


def dump_config(config: dict[str, Any]) -> str:
    """Format configuration dictionary into TOML string format."""
    merged = merge_defaults(config)
    runtfy_cfg = merged["runtfy"]
    quiet = merged["quiet_hours"]
    events = merged["events"]

    return (
        "[runtfy]\n"
        f'topic = "{runtfy_cfg["topic"]}"\n'
        f'summary = {str(bool(runtfy_cfg["summary"])).lower()}\n'
        f'summary_lines = {int(runtfy_cfg["summary_lines"])}\n'
        "\n"
        "[quiet_hours]\n"
        f'enabled = {str(bool(quiet["enabled"])).lower()}\n'
        f'start = "{quiet["start"]}"\n'
        f'end = "{quiet["end"]}"\n'
        "\n"
        "[events]\n"
        f'finish = {str(bool(events["finish"])).lower()}\n'
        f'waiting = {str(bool(events["waiting"])).lower()}\n'
    )


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Read configuration from file, returning defaults if missing or corrupted."""
    config_file = path if path is not None else get_config_path()
    if not config_file.is_file():
        return merge_defaults({})

    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
        return merge_defaults(data)
    except Exception:
        return merge_defaults({})


def write_config(config: dict[str, Any], path: Path | None = None) -> Path:
    """Write configuration file with owner-only permissions (mode 0o600).

    Args:
        config: Configuration dictionary to write.
        path: Target file path. Defaults to ~/.config/runtfy/config.toml.

    Returns:
        Path to the written configuration file.
    """
    target = path if path is not None else get_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target.parent, 0o700)
    except OSError:
        pass

    content = dump_config(config)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(target, flags, 0o600)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        os.close(fd)
        raise

    os.chmod(target, 0o600)
    return target


def init_config(
    path: Path | None = None,
    force: bool = False,
    prompt_fn: Callable[[str], str] | None = None,
) -> tuple[str, bool]:
    """Initialize configuration file with a generated ntfy topic.

    Args:
        path: Target file path. Defaults to ~/.config/runtfy/config.toml.
        force: If True, overwrite without prompting.
        prompt_fn: Input function for confirmation. Defaults to built-in input.

    Returns:
        tuple (topic, created_or_updated). If aborted, returns ("", False).
    """
    target = path if path is not None else get_config_path()
    if target.exists() and not force:
        ask = prompt_fn if prompt_fn is not None else input
        try:
            answer = ask(f"Config file already exists at {target}. Overwrite? [y/N]: ")
        except (EOFError, OSError):
            return "", False

        if answer.strip().lower() not in ("y", "yes"):
            return "", False

    topic = secrets.token_urlsafe(16)
    config = load_config(target)
    config["runtfy"]["topic"] = topic
    write_config(config, target)
    return topic, True
