"""Command-line entry point for runtfy."""

from __future__ import annotations

import sys
from typing import Sequence

from runtfy.config import init_config
from runtfy.hooks import handle_notify_hook, handle_stop_hook, install_hooks
from runtfy.locker import lock_and_watch
from runtfy.notifier import send_input_alert, send_lock_failed_alert
from runtfy.wrapper import run


def main(argv: Sequence[str] | None = None) -> None:
    """Run the runtfy CLI."""
    if argv is None:
        argv = sys.argv[1:]

    args_list = list(argv)
    lock_when_away = False
    if "--lock-when-away" in args_list:
        lock_when_away = True
        args_list.remove("--lock-when-away")

    if not args_list:
        sys.stderr.write("Usage: runtfy [--lock-when-away] <command> [args...]\n")
        sys.exit(1)

    if args_list[0] == "init":
        force = "-y" in args_list or "--force" in args_list
        topic, success = init_config(force=force)
        if not success:
            print("Aborted.")
            sys.exit(0)
        print(f"Open the ntfy app and subscribe to: {topic}")
        sys.exit(0)

    if args_list[0] == "install-hooks":
        install_hooks()
        sys.exit(0)

    if args_list[0] == "hook-stop":
        handle_stop_hook()
        sys.exit(0)

    if args_list[0] == "hook-notify":
        handle_notify_hook()
        sys.exit(0)

    stop_watcher = None
    if lock_when_away:
        def on_input_event(error: str | None = None) -> None:
            if error:
                send_lock_failed_alert(error)
            else:
                send_input_alert()

        stop_watcher = lock_and_watch(on_input_event)

    try:
        exit_code = run(args_list)
    finally:
        if stop_watcher:
            stop_watcher()

    sys.exit(exit_code)



if __name__ == "__main__":
    main()

