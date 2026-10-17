import os
import signal
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer

from nixos_updater.presentation.tray import NixOSUpdaterApp


class TraySignalTest(unittest.TestCase):
    def test_sigusr1_triggers_manual_check_while_idle(self):
        app = NixOSUpdaterApp([], "flake", "host", None, None, None)
        calls = []

        def fake_check(manual=False):
            calls.append((manual, time.monotonic()))
            app.quit()

        app._check_for_update = fake_check
        app._timer.stop()

        sent_at = []

        def send():
            sent_at.append(time.monotonic())
            os.kill(os.getpid(), signal.SIGUSR1)

        # sent from another thread so the main interpreter stays idle in exec()
        threading.Timer(0.3, send).start()
        QTimer.singleShot(3_000, app.quit)
        app.exec()

        self.assertEqual(len(calls), 1)
        manual, called_at = calls[0]
        self.assertTrue(manual)
        self.assertLess(called_at - sent_at[0], 1.0)


if __name__ == "__main__":
    unittest.main()
