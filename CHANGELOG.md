# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-30

- Package scaffolding configured with `hatchling` build system, Python >= 3.10 support, and CLI entrypoint.
- Pseudo-terminal (PTY) runner (`runtfy/wrapper.py`) supporting transparent stdin, stdout, and stderr passthrough with exact exit code propagation.
- Configuration manager (`runtfy/config.py`) loading settings from `~/.config/runtfy/config.toml` with owner-only (`0o600`) permissions and fallback defaults.
- `runtfy init` subcommand generating cryptographically random topics and writing owner-only configuration files.
- Resilient notification sender (`runtfy/notifier.py`) targeting ntfy via standard library `urllib.request` with 5-second timeout, quiet-hours suppression, event toggles, and strict topic sanitization.
- Finish notification integration delivering command completion alerts with program basename, elapsed duration, exit status, and opt-in truncated output summaries.
- Claude Code hook installer (`runtfy install-hooks`) supporting unified diff previews, automatic timestamped backups, and idempotent hook registration.
- Claude Code lifecycle handlers (`runtfy hook-stop` and `runtfy hook-notify`) providing completion summaries and user input alerts without blocking agent execution.
- Opt-in `--lock-when-away` mode on macOS utilizing native `pmset displaysleepnow` and `IOHIDSystem` input event monitoring with an enforced 60-second cooldown.
- Opt-in `--lock-when-away` session locking on Linux via `loginctl`, `xdg-screensaver`, and `gnome-screensaver-command` fallbacks.
- Comprehensive manual verification checklist (`LOCK_CHECKLIST.md`) for macOS and Linux lock modes.
