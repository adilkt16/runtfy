"""Pseudo-terminal wrapper for running commands interactively."""

from __future__ import annotations

import fcntl
import io
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import sys
import termios
import time
import tty
from typing import Any, Sequence

from runtfy.config import load_config
from runtfy import notifier


def _set_terminal_size(master_fd: int) -> None:
    """Set the window size of the pseudo-terminal to match current terminal."""
    try:
        size = shutil.get_terminal_size()
        winsize = struct.pack("HHHH", size.lines, size.columns, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except (OSError, ValueError):
        pass


def _write_all(fd: int, data: bytes) -> None:
    """Write all data bytes to a file descriptor."""
    while data:
        written = os.write(fd, data)
        data = data[written:]


def _write_stdout(data: bytes) -> None:
    """Write raw output bytes to stdout preserving formatting and supporting test runners."""
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(data.decode("utf-8", errors="replace"))
            sys.stdout.flush()
    except (io.UnsupportedOperation, AttributeError, OSError):
        try:
            os.write(1, data)
        except OSError:
            pass


def format_duration(seconds: float) -> str:
    """Format elapsed seconds into a human-readable string (e.g. '2m 34s', '5s')."""
    total_seconds = int(round(seconds))
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    rem_seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {rem_seconds}s"
    hours = minutes // 60
    rem_minutes = minutes % 60
    return f"{hours}h {rem_minutes}m {rem_seconds}s"


def send_finish_notification(
    cmd: Sequence[str],
    exit_code: int,
    duration_seconds: float,
    captured_output: str = "",
    config: dict[str, Any] | None = None,
) -> None:
    """Build and send a finish notification for a completed command.

    Args:
        cmd: Executed command and arguments.
        exit_code: Exit status code of the child process.
        duration_seconds: Elapsed execution duration in seconds.
        captured_output: Captured stdout text from the child process.
        config: Optional configuration dictionary. Defaults to loaded config.
    """
    if not cmd:
        return

    program_name = Path(cmd[0]).name
    status_str = "✓ success" if exit_code == 0 else f"✗ failed (code {exit_code})"
    duration_str = format_duration(duration_seconds)

    title = f"runtfy: {program_name} finished"
    body = f"Status: {status_str}\nDuration: {duration_str}"

    cfg = config if config is not None else load_config()
    runtfy_cfg = cfg.get("runtfy", {})
    if runtfy_cfg.get("summary", False) and captured_output:
        n_lines = int(runtfy_cfg.get("summary_lines", 5))
        # Strip ANSI escape codes and clean up carriage returns
        clean_text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", captured_output)
        lines = [line.strip("\r") for line in clean_text.splitlines() if line.strip("\r")]
        if lines:
            last_lines = lines[-n_lines:]
            body += "\n\n" + "\n".join(last_lines)

    if len(body) > 300:
        body = body[:297] + "..."

    try:
        notifier.send(title, body, event="finish", config=cfg)
    except Exception:
        # Never block the wrapper or change exit code on failure
        pass


def run(cmd: Sequence[str], config: dict[str, Any] | None = None) -> int:
    """Spawn a command inside a pseudo-terminal (PTY) and pass I/O through unchanged.

    Sends a finish notification on exit.

    Args:
        cmd: Command and arguments to execute, e.g. ["echo", "hello"].
        config: Optional configuration override.

    Returns:
        The exact exit code of the child process.
    """
    if not cmd:
        sys.stderr.write("runtfy: no command provided\n")
        return 1

    cmd_list = list(cmd)
    start_time = time.monotonic()
    output_chunks: list[bytes] = []

    try:
        pid, master_fd = pty.fork()
    except OSError as e:
        sys.stderr.write(f"runtfy: failed to create pseudo-terminal: {e}\n")
        return 1

    if pid == 0:
        # Child process: stdin, stdout, and stderr are connected to the slave PTY
        try:
            os.execvp(cmd_list[0], cmd_list)
        except FileNotFoundError:
            os.write(2, f"runtfy: command not found: {cmd_list[0]}\n".encode())
            os._exit(127)
        except PermissionError:
            os.write(2, f"runtfy: permission denied: {cmd_list[0]}\n".encode())
            os._exit(126)
        except Exception as e:
            os.write(2, f"runtfy: failed to execute {cmd_list[0]}: {e}\n".encode())
            os._exit(1)

    # Parent process
    _set_terminal_size(master_fd)

    old_sigwinch = None
    if hasattr(signal, "SIGWINCH"):
        def _handle_winch(signum: int, frame: object) -> None:
            _set_terminal_size(master_fd)

        try:
            old_sigwinch = signal.signal(signal.SIGWINCH, _handle_winch)
        except (ValueError, OSError):
            old_sigwinch = None

    stdin_fd: int | None = None
    try:
        if sys.stdin and hasattr(sys.stdin, "fileno") and not sys.stdin.closed:
            stdin_fd = sys.stdin.fileno()
    except (io.UnsupportedOperation, AttributeError, ValueError, OSError):
        stdin_fd = None

    stdin_is_atty = False
    old_term_settings = None
    if stdin_fd is not None:
        try:
            stdin_is_atty = os.isatty(stdin_fd)
        except Exception:
            stdin_is_atty = False

    if stdin_is_atty and stdin_fd is not None:
        try:
            old_term_settings = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)
        except (termios.error, OSError):
            old_term_settings = None

    read_fds = [master_fd]
    if stdin_fd is not None:
        read_fds.append(stdin_fd)

    try:
        while True:
            try:
                readable, _, _ = select.select(read_fds, [], [])
            except InterruptedError:
                continue
            except (ValueError, OSError):
                break

            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    data = b""

                if not data:
                    break

                output_chunks.append(data)
                _write_stdout(data)

            if stdin_fd is not None and stdin_fd in readable:
                try:
                    data = os.read(stdin_fd, 4096)
                except OSError:
                    data = b""

                if not data:
                    if stdin_fd in read_fds:
                        read_fds.remove(stdin_fd)
                    stdin_fd = None
                else:
                    try:
                        _write_all(master_fd, data)
                    except OSError:
                        break
    finally:
        if old_term_settings is not None and stdin_fd is not None:
            try:
                termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, old_term_settings)
            except (termios.error, OSError):
                pass

        if old_sigwinch is not None and hasattr(signal, "SIGWINCH"):
            try:
                signal.signal(signal.SIGWINCH, old_sigwinch)
            except (ValueError, OSError):
                pass

        try:
            os.close(master_fd)
        except OSError:
            pass

    # Wait for the child process to terminate and decode exit status
    while True:
        try:
            _, status = os.waitpid(pid, 0)
            break
        except InterruptedError:
            continue
        except ChildProcessError:
            status = 0
            break

    if os.WIFEXITED(status):
        exit_code = os.WEXITSTATUS(status)
    elif os.WIFSIGNALED(status):
        exit_code = 128 + os.WTERMSIG(status)
    else:
        exit_code = 1

    duration = time.monotonic() - start_time
    output_text = b"".join(output_chunks).decode("utf-8", errors="replace")

    send_finish_notification(
        cmd=cmd_list,
        exit_code=exit_code,
        duration_seconds=duration,
        captured_output=output_text,
        config=config,
    )

    return exit_code
