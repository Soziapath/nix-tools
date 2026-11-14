"""Private, ephemeral loopback bridge between a Noctalia panel and an SSH PTY."""
import fcntl
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import pty
import re
import secrets
import select
import signal
import subprocess
import termios
import threading
import time

from unlock import session_lock_path, ssh_command

PROMPT = re.compile(rb"Please unlock disk ([^:\r\n]{1,200}):\s*")


class Session:
    def __init__(self, args):
        self.args = args
        self.guard = threading.Lock()
        self.state = {"status": "connecting", "message": "Connecting to the unlock server…", "attempt": 0}
        self.stop = threading.Event()
        self.prompt = threading.Event()
        self.fd = None

    def password(self, value):
        with self.guard:
            if self.state["status"] != "password" or not isinstance(value, str) or not value or any(c in value for c in "\r\n\x00"):
                return False
            raw = value.encode("utf-8")
            if len(raw) > 4096:
                return False
            settings = termios.tcgetattr(self.fd)
            settings[3] &= ~(termios.ECHO | termios.ECHONL)
            termios.tcsetattr(self.fd, termios.TCSANOW, settings)
            os.write(self.fd, raw + b"\n")
            self.state.update(status="working", message="Unlocking the disk…")
            return True

    def run(self):
        process = None
        slave = None
        try:
            self.fd, slave = pty.openpty()
            settings = termios.tcgetattr(slave)
            settings[3] &= ~(termios.ECHO | termios.ECHONL)
            termios.tcsetattr(slave, termios.TCSANOW, settings)
            command = ssh_command(self.args)
            command[1] = "-tt"
            command[2:2] = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "EscapeChar=none"]
            process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            slave = None
            buffer = b""
            while not self.stop.is_set():
                if select.select([self.fd], [], [], 0.2)[0]:
                    try:
                        chunk = os.read(self.fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buffer = (buffer + chunk)[-8192:]
                    match = PROMPT.search(buffer)
                    if match:
                        with self.guard:
                            self.state.update(status="password", message="Enter the passphrase for " + match[1].decode("utf-8", "replace"), attempt=self.state["attempt"] + 1)
                        self.prompt.set()
                        buffer = buffer[match.end():]
                if process.poll() is not None:
                    break
            if self.stop.is_set():
                return
            code = process.wait(timeout=5)
            with self.guard:
                self.state.update(status="success" if code == 0 else "error", message="Unlock command completed successfully." if code == 0 else "SSH closed without completing the unlock. Check the server, trusted host key, and SSH identity (encrypted keys must be loaded in ssh-agent).")
        except Exception:
            with self.guard:
                self.state.update(status="error", message="Unable to run the SSH unlock session.")
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            if slave is not None:
                os.close(slave)
            if self.fd is not None:
                os.close(self.fd)


def prompt_available(args):
    """Check for a disk prompt, then close SSH without sending input."""
    session = Session(args)
    finished = threading.Event()

    def run_probe():
        try:
            session.run()
        finally:
            finished.set()

    worker = threading.Thread(target=run_probe, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + args.timeout + 2
        while not session.prompt.is_set() and not finished.wait(0.1):
            if time.monotonic() >= deadline:
                break
        return session.prompt.is_set()
    finally:
        session.stop.set()
        worker.join(timeout=3)


def serve(args):
    path = session_lock_path(args)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"error": "An unlock session is already open."}), flush=True)
            return 75
        session = Session(args)
        # Stream teardown must also stop SSH, which owns a separate process group.
        signal.signal(signal.SIGTERM, lambda *_: session.stop.set())
        signal.signal(signal.SIGINT, lambda *_: session.stop.set())
        signal.signal(signal.SIGHUP, lambda *_: session.stop.set())
        token = secrets.token_urlsafe(32)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_request(self):
                self.connection.settimeout(3)
                if self.headers.get("Origin") or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                    self.send_error(403)
                    return
                if self.command == "POST":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 32768:
                            raise ValueError()
                        data = json.loads(self.rfile.read(length))
                        if self.path == "/password":
                            if not session.password(data.get("password")):
                                self.send_error(409)
                                return
                        elif self.path == "/cancel":
                            session.stop.set()
                        else:
                            self.send_error(404)
                            return
                    except (ValueError, OSError, AttributeError):
                        self.send_error(400)
                        return
                elif self.path != "/state":
                    self.send_error(404)
                    return
                with session.guard:
                    body = json.dumps(session.state).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = handle_request
            do_POST = handle_request

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            server.timeout = 0.2
            print(json.dumps({"port": server.server_port, "token": token}), flush=True)
            worker = threading.Thread(target=session.run, daemon=True)
            worker.start()
            deadline = time.monotonic() + 600
            try:
                while not session.stop.is_set() and time.monotonic() < deadline:
                    server.handle_request()
            finally:
                session.stop.set()
                worker.join(timeout=5)
    return 0
