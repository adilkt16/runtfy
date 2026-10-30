"""Tests for runtfy config loading, serialization, and init subcommand."""

from pathlib import Path
import pytest

from runtfy.cli import main
from runtfy.config import (
    DEFAULT_CONFIG,
    init_config,
    load_config,
    write_config,
)


def test_missing_config_returns_defaults(tmp_path: Path) -> None:
    """A missing config file does not raise an exception; defaults are returned."""
    missing_file = tmp_path / "nonexistent_config.toml"
    assert not missing_file.exists()

    config = load_config(missing_file)
    assert config == DEFAULT_CONFIG
    assert config["runtfy"]["topic"] == ""
    assert config["runtfy"]["summary"] is False
    assert config["runtfy"]["summary_lines"] == 5
    assert config["quiet_hours"]["enabled"] is False
    assert config["quiet_hours"]["start"] == "22:00"
    assert config["quiet_hours"]["end"] == "08:00"
    assert config["events"]["finish"] is True
    assert config["events"]["waiting"] is True


def test_parse_minimal_toml_returns_defaults(tmp_path: Path) -> None:
    """Parsing a minimal TOML file returns correct defaults for missing keys."""
    minimal_file = tmp_path / "minimal.toml"
    minimal_file.write_text(
        '[runtfy]\ntopic = "sample-topic-placeholder"\n',
        encoding="utf-8",
    )

    config = load_config(minimal_file)
    assert config["runtfy"]["topic"] == "sample-topic-placeholder"
    # Verify missing keys in [runtfy] defaulted correctly
    assert config["runtfy"]["summary"] is False
    assert config["runtfy"]["summary_lines"] == 5
    # Verify missing sections defaulted correctly
    assert config["quiet_hours"]["enabled"] is False
    assert config["quiet_hours"]["start"] == "22:00"
    assert config["quiet_hours"]["end"] == "08:00"
    assert config["events"]["finish"] is True
    assert config["events"]["waiting"] is True


def test_write_config_creates_file_with_mode_0o600(tmp_path: Path) -> None:
    """Writing the config creates a file with mode 0o600."""
    target_file = tmp_path / "sub" / "config.toml"
    written_path = write_config(DEFAULT_CONFIG, target_file)

    assert written_path == target_file
    assert target_file.is_file()
    mode = target_file.stat().st_mode & 0o777
    assert mode == 0o600

    # Ensure written content is valid TOML and round-trips correctly
    reloaded = load_config(target_file)
    assert reloaded == DEFAULT_CONFIG


def test_init_config_creates_new_topic_and_file(tmp_path: Path) -> None:
    """init_config generates a random topic and writes owner-only file."""
    target_file = tmp_path / "new_config.toml"
    topic, ok = init_config(target_file)

    assert ok is True
    assert len(topic) >= 16
    assert target_file.is_file()
    assert (target_file.stat().st_mode & 0o777) == 0o600

    loaded = load_config(target_file)
    assert loaded["runtfy"]["topic"] == topic


def test_init_config_prompts_on_existing_file(tmp_path: Path) -> None:
    """init_config asks before overwriting an existing config file."""
    target_file = tmp_path / "existing.toml"
    topic1, _ = init_config(target_file)

    # User declines overwrite
    topic2, ok = init_config(target_file, prompt_fn=lambda _: "n")
    assert ok is False
    assert topic2 == ""
    assert load_config(target_file)["runtfy"]["topic"] == topic1

    # User confirms overwrite
    topic3, ok3 = init_config(target_file, prompt_fn=lambda _: "y")
    assert ok3 is True
    assert topic3 != ""
    assert topic3 != topic1
    assert load_config(target_file)["runtfy"]["topic"] == topic3


def test_cli_init_subcommand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """runtfy init CLI command creates config and prints subscribe instruction."""
    target_file = tmp_path / "config.toml"
    monkeypatch.setattr("runtfy.config.get_config_path", lambda: target_file)

    with pytest.raises(SystemExit) as exc_info:
        main(["init"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Open the ntfy app and subscribe to: " in captured.out
    assert target_file.is_file()
    assert (target_file.stat().st_mode & 0o777) == 0o600
