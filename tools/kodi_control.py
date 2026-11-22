#!/usr/bin/env python3
"""Launch and operate the development Kodi window on X11."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
KEYS = {"up": "Up", "down": "Down", "left": "Left", "right": "Right",
        "select": "Return", "back": "BackSpace", "home": "Escape", "stop": "x", "space": "space"}
WINDOW_HELP = "window ID from list"


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def windows() -> list[str]:
    result = command("xdotool", "search", "--onlyvisible", "--class", "Kodi", check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "Could not search for Kodi windows")
    return result.stdout.split()


def select_window(window: str) -> str:
    try:
        identifier = str(int(window, 0))
    except ValueError as invalid:
        raise RuntimeError("Window ID must be a decimal or hexadecimal number") from invalid
    if identifier not in windows():
        raise RuntimeError("The selected window is not a visible Kodi window")
    return identifier


def start() -> None:
    existing = command("pgrep", "-u", str(os.getuid()), "-f", "/kodi.bin", check=False)
    if existing.returncode not in (0, 1):
        raise RuntimeError(existing.stderr.strip() or "Could not check running Kodi processes")
    if windows() or existing.returncode == 0:
        raise RuntimeError("Kodi is already running; use list and select its window instead")
    cache = Path.home() / ".cache" / "yle-arenan-kodi"
    cache.mkdir(parents=True, exist_ok=True)
    log_path = cache / "kodi-launch.log"
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as log:
        process = subprocess.Popen(["bash", str(PROJECT / "tools" / "run-kodi.sh")],
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Kodi launcher exited with {process.returncode}; see {log_path}")
        found = windows()
        if len(found) == 1:
            print(f"Kodi window: {found[0]}")
            return
        if len(found) > 1:
            raise RuntimeError("Multiple Kodi windows appeared; use list to select one")
        time.sleep(0.25)
    raise RuntimeError(f"Kodi window did not appear; see {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("start", help="deploy and start Kodi if it is not already running")
    actions.add_parser("list", help="list visible Kodi windows")
    key_parser = actions.add_parser("key", help="send navigation keys to a Kodi window")
    key_parser.add_argument("--window", required=True, help=WINDOW_HELP)
    key_parser.add_argument("keys", nargs="+", choices=KEYS)
    type_parser = actions.add_parser("type", help="type text into a Kodi input dialog")
    type_parser.add_argument("--window", required=True, help=WINDOW_HELP)
    type_parser.add_argument("text")
    capture_parser = actions.add_parser("screenshot", help="capture a Kodi window as PNG")
    capture_parser.add_argument("--window", required=True, help=WINDOW_HELP)
    capture_parser.add_argument("--output", type=Path, help="PNG path (default: a temporary file)")
    args = parser.parse_args()

    if args.action == "start":
        start()
    elif args.action == "list":
        for window in windows():
            name = command("xdotool", "getwindowname", window).stdout.strip()
            print(f"{window}\t{name}")
    elif args.action == "key":
        window = select_window(args.window)
        for key in args.keys:
            command("xdotool", "key", "--window", window, KEYS[key])
            time.sleep(0.15)
    elif args.action == "type":
        window = select_window(args.window)
        command("xdotool", "type", "--window", window, "--delay", "100", "--", args.text)
    else:
        window = select_window(args.window)
        output = args.output or Path(tempfile.gettempdir()) / f"kodi-{uuid.uuid4().hex}.png"
        if output.suffix.lower() != ".png":
            raise RuntimeError("Screenshot output must have a .png extension")
        display = os.environ.get("DISPLAY")
        if not display:
            raise RuntimeError("DISPLAY must identify an X11 display")
        previous_umask = os.umask(0o077)
        try:
            command("ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-f", "x11grab",
                    "-window_id", window, "-i", display, "-frames:v", "1", str(output))
        finally:
            os.umask(previous_umask)
        print(output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        stderr = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else ""
        print(f"Error: {stderr or error}", file=sys.stderr)
        sys.exit(1)
