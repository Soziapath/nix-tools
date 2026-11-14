import argparse
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from gui_bridge import Session, PROMPT, prompt_available

class GuiTests(unittest.TestCase):
    def test_availability_requires_a_disk_prompt_and_closes_session(self):
        for output, expected in [
            ("SSH is up, but the disk is unlocked", False),
            ("Please unlock disk data_crypt: ", True),
        ]:
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                script = Path(directory) / "fake-ssh"
                script.write_text("#!/bin/sh\nprintf '%s' \"$1\"\n" if not expected else
                                  "#!/bin/sh\nprintf 'Please unlock disk data_crypt: '\nread -r ignored\n")
                script.chmod(0o700)
                with patch("gui_bridge.ssh_command", return_value=[str(script), "-t", output]):
                    self.assertEqual(prompt_available(argparse.Namespace(timeout=0.2)), expected)

    def test_only_disk_prompt_is_recognized(self):
        self.assertIsNone(PROMPT.search(b"root password: "))
        self.assertIsNone(PROMPT.search(b"Enter passphrase for key: "))
        self.assertIsNotNone(PROMPT.search(b"Please unlock disk sdg3_crypt: "))

    def test_real_pty_prompt_retry_password_and_success(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'fake-ssh'
            script.write_text('#!/bin/sh\nprintf "Please unlock disk sdg3_crypt: "\nIFS= read -r first\nprintf "Wrong password\\nPlease unlock disk sdg3_crypt: "\nIFS= read -r second\n[ "$second" = "correct horse" ]\n')
            script.chmod(0o700)
            session = Session(argparse.Namespace())
            with patch('gui_bridge.ssh_command', return_value=[str(script), '-t']):
                worker = threading.Thread(target=session.run)
                worker.start()
                def wait_for(status, attempt=None):
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        with session.guard:
                            if session.state['status'] == status and (attempt is None or session.state['attempt'] == attempt): return
                        time.sleep(0.01)
                    self.fail(str(session.state))
                try:
                    wait_for('password', 1)
                    self.assertFalse(session.password('bad\ninput'))
                    self.assertTrue(session.password('wrong'))
                    wait_for('password', 2)
                    self.assertTrue(session.password('correct horse'))
                    wait_for('success')
                finally:
                    session.stop.set()
                    worker.join(timeout=4)
                self.assertFalse(worker.is_alive())
