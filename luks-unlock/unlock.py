#!/usr/bin/env python3
"""Wait for an SSH unlock endpoint, then give OpenSSH the real terminal."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time


def positive(value):
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def ssh_available(host, port, timeout):
    """Read a bounded SSH identification banner without authenticating."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            deadline = time.monotonic() + timeout
            data = b""
            for _ in range(4096):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                connection.settimeout(remaining)
                byte = connection.recv(1)
                if not byte:
                    return False
                data += byte
                if byte == b"\n":
                    if data.startswith((b"SSH-2.0-", b"SSH-1.99-")):
                        return True
                    data = b""
    except OSError:
        pass
    return False


def ssh_command(args):
    return [
        "ssh", "-t", "-i", str(args.identity), "-p", str(args.port),
        "-o", "IdentitiesOnly=yes",
        "-o", f"ConnectTimeout={max(1, int(args.timeout))}",
        "-o", "ConnectionAttempts=1",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=3",
        f"{args.user}@{args.host}", "cryptroot-unlock",
    ]


def session_lock_path(args):
    import hashlib

    cache = Path(os.environ.get("XDG_RUNTIME_DIR", Path.home() / ".cache")) / "luks-unlock"
    endpoint = hashlib.sha256(f"{args.host}:{args.port}".encode()).hexdigest()[:24]
    return cache / f"{endpoint}.lock"


def session_active(args):
    import fcntl

    try:
        with session_lock_path(args).open("r+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return False
            except BlockingIOError:
                return True
    except FileNotFoundError:
        return False


class UI:
    def __init__(self):
        self.animated = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"
        self.color = self.animated and "NO_COLOR" not in os.environ

    def heading(self, endpoint):
        title = "\033[1;36mLUKS unlock\033[0m" if self.color else "LUKS unlock"
        print(f"\n  {title}\n  {endpoint}\n\n  Waiting for initramfs SSH. Ctrl+C cancels.\n", flush=True)

    def status(self, message):
        if self.animated:
            print(f"\r\033[2K{message}", end="", flush=True)
        else:
            print(message, flush=True)

    def newline(self):
        if self.animated:
            print(flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="luks-unlock", description=__doc__)
    parser.add_argument("host", help="initramfs SSH hostname or address")
    parser.add_argument("-p", "--port", type=int, default=2222)
    parser.add_argument("-i", "--identity", type=lambda p: Path(p).expanduser(),
                        default=Path("~/.ssh/luks-unlock").expanduser())
    parser.add_argument("-u", "--user", default="root")
    parser.add_argument("--interval", type=positive, default=2, help="seconds between checks (default: 2)")
    parser.add_argument("--timeout", type=positive, default=3, help="connection timeout in seconds (default: 3)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check once without a terminal or authentication (exit 0: available, 1: unavailable)")
    mode.add_argument("--check-unlock", action="store_true", help="verify that cryptroot-unlock is asking for a disk passphrase")
    mode.add_argument("--terminal", action="store_true", help="open in Kitty, allowing only one unlock window per endpoint")
    mode.add_argument("--gui", action="store_true", help="start the private Noctalia panel bridge")
    parser.add_argument("--json", action="store_true", help="emit JSON with --check")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not args.host or args.host.startswith("-") or args.user.startswith("-") or "@" in args.user:
        parser.error("invalid host or user")
    if args.json and not (args.check or args.check_unlock):
        parser.error("--json requires a check mode")
    if args.check or args.check_unlock:
        unlocking = (args.json or args.check_unlock) and session_active(args)
        available = ssh_available(args.host, args.port, args.timeout)
        if args.check_unlock:
            from gui_bridge import prompt_available
            available = available and not unlocking and prompt_available(args)
        if args.json:
            print(json.dumps({"available": available, "host": args.host,
                              "port": args.port, "checked_at": int(time.time()),
                              "unlocking": unlocking}))
        else:
            print("Unlock available" if available else "Unlock endpoint unavailable")
        return 0 if available else 1
    if args.terminal:
        return open_terminal(args)
    if args.gui:
        from gui_bridge import serve
        return serve(args)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("run in an interactive terminal so SSH can accept the unlock passphrase")
    if not args.identity.is_file():
        parser.error(f"identity file does not exist: {args.identity}")
    if not shutil.which("ssh"):
        parser.error("OpenSSH is missing; run inside nix develop")

    ui = UI()
    ui.heading(f"{args.user}@{args.host}:{args.port}")
    checks = 0
    try:
        while True:
            checks += 1
            ui.status(f"  {'◐◓◑◒'[checks % 4]} Checking unlock endpoint · attempt {checks}")
            if ssh_available(args.host, args.port, args.timeout):
                ui.newline()
                print("\n  SSH is ready. Opening interactive unlock session…\n", flush=True)
                result = subprocess.run(ssh_command(args), check=False)
                if result.returncode == 0:
                    print("\n  Unlock command completed successfully.\n", flush=True)
                    return 0
                print(f"\n  SSH exited with status {result.returncode}. Retrying; Ctrl+C exits.\n", flush=True)
            else:
                ui.status(f"  Waiting for SSH · check {checks} · retry in {args.interval:g}s")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        ui.newline()
        print("\n  Cancelled.")
        return 130


def open_terminal(args):
    """Hold a per-endpoint lock until the interactive Kitty window closes."""
    import fcntl

    path = session_lock_path(args)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("An unlock window is already open for this endpoint.", file=sys.stderr)
            return 75
        command = ["kitty", "--class", "luks-unlock", "--title", f"Unlock {args.host}", "-e",
                   sys.executable, str(Path(__file__).resolve()), args.host,
                   "-p", str(args.port), "-i", str(args.identity), "-u", args.user,
                   "--interval", str(args.interval), "--timeout", str(args.timeout)]
        try:
            return subprocess.run(command, check=False).returncode
        except OSError as error:
            print(f"Cannot open unlock terminal: {error}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
