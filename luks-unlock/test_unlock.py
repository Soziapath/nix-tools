import argparse
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import unlock


class UnlockTests(unittest.TestCase):
    def probe(self, banner):
        connection = MagicMock()
        connection.recv.side_effect = [bytes([byte]) for byte in banner] + [b""]
        connection.__enter__.return_value = connection
        with patch("unlock.socket.create_connection", return_value=connection):
            return unlock.ssh_available("host", 2222, 1)

    def test_ssh_banner_after_notice(self):
        self.assertTrue(self.probe(b"Notice\r\nSSH-2.0-dropbear\r\n"))

    def test_non_ssh_service_and_closed_connection(self):
        self.assertFalse(self.probe(b"HTTP/1.1 200 OK\r\n"))
        self.assertFalse(self.probe(b""))

    def test_unreachable_endpoint(self):
        with patch("unlock.socket.create_connection", side_effect=socket.timeout):
            self.assertFalse(unlock.ssh_available("host", 2222, 1))

    def test_command_preserves_interactive_terminal_and_host_verification(self):
        args = argparse.Namespace(identity=Path("/key with spaces"), port=2222,
                                  timeout=3, user="root", host="proxmox.example.test")
        command = unlock.ssh_command(args)
        self.assertEqual(command[:6], ["ssh", "-t", "-i", "/key with spaces", "-p", "2222"])
        self.assertEqual(command[-2:], ["root@proxmox.example.test", "cryptroot-unlock"])
        self.assertFalse(any("StrictHostKeyChecking" in arg for arg in command))

    def test_json_probe_needs_neither_terminal_nor_identity_file(self):
        for available in (True, False):
            output = io.StringIO()
            with patch("unlock.ssh_available", return_value=available), patch("unlock.session_active", return_value=False), contextlib.redirect_stdout(output):
                status = unlock.main(["--check", "--json", "--identity", "/missing/key", "proxmox.example.test"])
            self.assertEqual(status, 0 if available else 1)
            self.assertEqual(json.loads(output.getvalue())["available"], available)

    def test_session_lock_reports_active_and_releases_after_close(self):
        args = argparse.Namespace(host="host", port=2222)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
            self.assertFalse(unlock.session_active(args))
            path = unlock.session_lock_path(args)
            path.parent.mkdir()
            with path.open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertTrue(unlock.session_active(args))
            self.assertFalse(unlock.session_active(args))

    def test_duplicate_terminal_is_rejected(self):
        args = argparse.Namespace(host="host", port=2222)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
            path = unlock.session_lock_path(args)
            path.parent.mkdir()
            with path.open("a") as lock, patch("unlock.subprocess.run") as run, contextlib.redirect_stderr(io.StringIO()):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(unlock.open_terminal(args), 75)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
