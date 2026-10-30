# runtfy: Product Requirements (v0.1)

Status: Draft for v0.1.0
License: MIT

## Summary

runtfy is an open source command-line tool. It wraps a terminal command, such as a coding agent run, and sends a notification to your phone when the command finishes or when Claude Code needs input. It can also lock your screen while you are away and alert you if anyone types or moves the mouse.

## Problem

Developers start long coding-agent runs and walk away. They later find out the agent finished in five minutes and sat idle for forty, or that it stopped to ask for permission and never continued. There is no simple way to get that signal on a phone across tools.

## Target users

Developers who run long AI coding-agent sessions from a terminal on macOS or Linux, and who step away during runs.

## Goals

- Notify the user's phone when a wrapped command finishes, with the program name, exit status, and duration.
- Notify the user when Claude Code is waiting for permission or input.
- Let any terminal command be wrapped, not only Claude Code.
- Offer an opt-in lock-when-away mode that locks the screen and alerts on input while locked.
- Install in under five minutes, with no accounts or servers required from the user.

## Non-goals for v0.1

- Replying to or approving agent prompts from the phone (planned for v0.2).
- Windows support.
- Input alerts on Linux. Linux gets the lock only in v0.1.
- Camera capture, photos, or location tracking.
- Lid-open or motion-based theft detection.
- A hosted service, dashboard, accounts, or mobile app.
- Cursor and Codex integration.
- Lock-when-away as a default behavior.

## Scope decisions

- Platforms: macOS and Linux.
- Agents: Claude Code through its hooks. Any other command gets the finish notification only.
- Delivery: ntfy. The project runs no server. Each user picks a random topic name.
- Lock-when-away: opt-in with the flag --lock-when-away. On macOS it locks and alerts on input. On Linux it locks only.

## Privacy and security

- Default notifications contain only the program name (for example, "claude", not its arguments), exit code, duration, and success or failure. Arguments are never shown, because they can contain secrets.
- No command output, file paths, or file contents appear in notifications by default.
- Output summaries are opt-in through the config setting summary = true. The README warns that summaries can expose sensitive content.
- The ntfy topic is the only secret. runtfy generates it locally, stores it in the user's config file, and never prints it in logs or commits it.
- runtfy never stores, reads, or transmits the OS password. Unlocking is always handled by the OS.
- No telemetry. The only network traffic goes to the configured ntfy server.
- The repo contains no personal names, emails, usernames, or machine paths. Examples use placeholders such as your-topic-here and ~/.config/runtfy.
- Config files and .env files are gitignored.

## User stories

1. As a developer, I start a long agent run and get a phone notification when it finishes, so I know when to return.
2. As a developer, I get a phone notification when Claude Code is waiting for my permission, so I am not blocked for an hour.
3. As a developer, I can wrap any command with runtfy and get the same finish notification.
4. As a developer who is away, I can run runtfy with --lock-when-away to lock my screen, and I get alerted if someone types or moves the mouse while it is locked.
5. As a developer, I can set my topic, quiet hours, and which events notify in one config file.

## Functional requirements

- FR1: The wrapper runs the command in a pseudo-terminal and passes input and output through unchanged.
- FR2: The wrapper exits with the wrapped command's exit code.
- FR3: On exit, runtfy sends a notification with the program name, exit code, duration, and status. If summary = true, it also includes the last N lines of output (default 5).
- FR4: For Claude Code, a Stop hook sends a finished notification. If summary = true, it includes the final message, truncated to 300 characters.
- FR5: For Claude Code, a Notification hook sends an alert that Claude Code needs input.
- FR6: runtfy install-hooks adds the Stop and Notification hooks to the Claude Code settings file. It shows a diff, asks for confirmation, creates a backup first, never removes existing hooks, and is safe to run twice.
- FR7: --lock-when-away locks the screen at start using the OS lock, and watches for input while locked.
- FR8: Input alerts while locked have a 60-second cooldown.
- FR9: Config lives at ~/.config/runtfy/config.toml. It holds the topic, summary setting, summary line count, quiet hours, and event toggles.
- FR10: runtfy init generates a random topic, writes the config file with owner-only permissions, and prints subscribe steps for the ntfy app.
- FR11: If notification delivery fails or times out after 5 seconds, the wrapped command is not affected. The failure is logged locally without the topic.
- FR12: If locking fails, the command still runs and the user is notified that the screen is unlocked.

## Non-functional requirements

- Privacy: follows the Privacy and security section above.
- Reliability: runtfy never hangs or crashes the wrapped command because of notifications or locking.
- Install: pipx install works on macOS and Linux with Python 3.10 or later.
- Tests: unit tests for message formatting, config parsing, hook file handling, and the wrapper's exit code. Lock behavior is covered by a manual checklist.

## Build order

Build these tasks in order. Each task is one unit of work, and the next task starts only after the previous one passes.

1. Scaffold: package layout, pyproject.toml with a runtfy command entry point, and one passing placeholder test.
2. Wrapper: pseudo-terminal runner with passthrough and exit code handling. Tests included.
3. Config and delivery: config file, runtfy init, ntfy sender with timeout and local failure logging.
4. Finish notification: program name, exit code, duration, status, and opt-in summary.
5. Claude Code hooks: runtfy install-hooks with diff, confirmation, backup, and the Stop and Notification handlers.
6. Lock-when-away: the --lock-when-away flag, macOS and Linux paths, and input watching on macOS.
7. Docs: README, CONTRIBUTING, and CHANGELOG. All examples use placeholders.
8. CI: GitHub Actions workflow that runs tests on every push.
9. Package check: build the package and confirm the runtfy command works from a clean virtualenv in another directory.

## Implementation rules

- Never hardcode a topic, token, username, email, or home directory path. Read them from the config file or environment variables.
- Never print or log the ntfy topic.
- Make no network calls except to the configured ntfy server.
- Use placeholders in all examples and docs.
- Write tests for each change and run them before reporting a task as done.
- Do only the current task. Do not start later tasks.
- Ask before adding a dependency.

## Success metrics (first 30 days)

- A new user gets their first phone notification within 5 minutes of installing.
- 10 active installs reported in issues or discussions.
- Zero reports of runtfy blocking or breaking a wrapped command. This is the most important metric.
- At least 3 external issues or pull requests.

## Risks

- Claude Code hook payloads or settings format change. Mitigation: state the tested version range in the README and retest on each release.
- macOS lock and idle-time commands change between versions. Mitigation: test on the current and previous macOS release before tagging.
- Users get locked out or confused by lock mode. Mitigation: opt-in only, a warning on first use, and clear limits in the README.
- Built-in notifications from Claude Code or other tools make this redundant. Mitigation: ship fast, keep scope small, and learn from real usage.
- The public ntfy server rate-limits heavy use. Mitigation: document self-hosting ntfy.
- The name "runtfy" conflicts with an existing package. Mitigation: check PyPI, GitHub, and npm before the first release, and rename in one pass if needed.

## Release criteria for v0.1.0

- All functional requirements pass manual testing on macOS and Linux.
- The lock checklist passes on one current macOS version and one Linux distribution.
- README covers install, quick start, ntfy setup, lock limits, and privacy notes.
- A secret scan of the full git history finds nothing.
- CI runs tests on every push.
