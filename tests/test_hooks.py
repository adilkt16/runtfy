"""Tests for the Claude Code hook installation module."""

import json
from pathlib import Path
import pytest

from runtfy.cli import main
from runtfy.hooks import install_hooks


def test_install_hooks_empty_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Running install-hooks on an empty settings file creates correct hook entries."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}", encoding="utf-8")

    success = install_hooks(settings_file, prompt_fn=lambda _: "y")
    assert success is True

    captured = capsys.readouterr()
    assert "Hooks installed. Run runtfy init if you haven't already." in captured.out

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "hooks" in data
    assert "Stop" in data["hooks"]
    assert "Notification" in data["hooks"]

    # Verify Stop hook
    stop_cmds = [h["command"] for item in data["hooks"]["Stop"] for h in item.get("hooks", [])]
    assert "runtfy hook-stop" in stop_cmds

    # Verify Notification hook
    notify_cmds = [h["command"] for item in data["hooks"]["Notification"] for h in item.get("hooks", [])]
    assert "runtfy hook-notify" in notify_cmds


def test_install_hooks_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Running it twice does not duplicate hooks (idempotent)."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}", encoding="utf-8")

    # First run
    success1 = install_hooks(settings_file, prompt_fn=lambda _: "y")
    assert success1 is True

    data1 = json.loads(settings_file.read_text(encoding="utf-8"))
    stop_count1 = len(data1["hooks"]["Stop"])
    notify_count1 = len(data1["hooks"]["Notification"])
    assert stop_count1 == 1
    assert notify_count1 == 1

    # Second run
    capsys.readouterr()
    success2 = install_hooks(settings_file, prompt_fn=lambda _: "y")
    assert success2 is True

    captured2 = capsys.readouterr()
    assert "Hooks already installed." in captured2.out

    data2 = json.loads(settings_file.read_text(encoding="utf-8"))
    assert len(data2["hooks"]["Stop"]) == stop_count1
    assert len(data2["hooks"]["Notification"]) == notify_count1


def test_install_hooks_creates_backup(tmp_path: Path) -> None:
    """A timestamped backup file is created before writing."""
    settings_file = tmp_path / "settings.json"
    original_content = json.dumps({"model": "opus", "theme": "dark"}, indent=2) + "\n"
    settings_file.write_text(original_content, encoding="utf-8")

    success = install_hooks(settings_file, prompt_fn=lambda _: "y")
    assert success is True

    # Check that a backup file matching settings.json.*.bak exists
    backup_files = list(tmp_path.glob("settings.json.*.bak"))
    assert len(backup_files) == 1
    assert backup_files[0].read_text(encoding="utf-8") == original_content

    # Check updated settings preserves original fields
    updated_data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert updated_data["model"] == "opus"
    assert updated_data["theme"] == "dark"
    assert "hooks" in updated_data


def test_install_hooks_diff_shown_and_aborted_on_n(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The diff is shown and the command does nothing if the user types 'n'."""
    settings_file = tmp_path / "settings.json"
    original_content = json.dumps({"custom_setting": 123}, indent=2) + "\n"
    settings_file.write_text(original_content, encoding="utf-8")

    success = install_hooks(settings_file, prompt_fn=lambda _: "n")
    assert success is False

    captured = capsys.readouterr()
    # Check that diff is shown
    assert "---" in captured.out
    assert "+++" in captured.out
    assert "runtfy hook-stop" in captured.out
    assert "Aborted." in captured.out

    # Check that file was not modified
    assert settings_file.read_text(encoding="utf-8") == original_content

    # Check that no backup file was created
    backup_files = list(tmp_path.glob("settings.json.*.bak"))
    assert len(backup_files) == 0


def test_install_hooks_preserves_existing_hooks(tmp_path: Path) -> None:
    """Existing hooks in other events or within Stop/Notification are never removed."""
    settings_file = tmp_path / "settings.json"
    initial_settings = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {"type": "command", "command": "echo 'custom stop'"}
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "hooks": [
                        {"type": "command", "command": "echo 'pre tool'"}
                    ]
                }
            ],
        }
    }
    settings_file.write_text(json.dumps(initial_settings, indent=2), encoding="utf-8")

    success = install_hooks(settings_file, prompt_fn=lambda _: "y")
    assert success is True

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "PreToolUse" in data["hooks"]
    stop_cmds = [h["command"] for item in data["hooks"]["Stop"] for h in item.get("hooks", [])]
    assert "echo 'custom stop'" in stop_cmds
    assert "runtfy hook-stop" in stop_cmds


def test_cli_install_hooks_subcommand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """runtfy install-hooks runs via CLI entrypoint."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("runtfy.hooks.get_claude_settings_path", lambda: settings_file)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    with pytest.raises(SystemExit) as exc_info:
        main(["install-hooks"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Hooks installed." in captured.out
    assert settings_file.is_file()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "hooks" in data
