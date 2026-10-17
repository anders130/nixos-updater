import subprocess
import unittest
from unittest import mock

from nixos_updater.domain.models import Revision
from nixos_updater.infrastructure.nix_cli import CurrentSystemRevision

REV = "c" * 40


def _run(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


class CurrentSystemRevisionTest(unittest.TestCase):
    def _revision(self, **kwargs):
        with mock.patch("subprocess.run", return_value=_run(**kwargs)):
            return CurrentSystemRevision().running_revision()

    def test_clean_revision(self):
        self.assertEqual(self._revision(stdout=REV + "\n"), Revision(REV))

    def test_unset_revision(self):
        # nixos-version exits 1 with "configuration revision is unknown".
        self.assertIsNone(self._revision(returncode=1))

    def test_empty_or_null(self):
        self.assertIsNone(self._revision(stdout="\n"))
        self.assertIsNone(self._revision(stdout="null\n"))

    def test_dirty_revision(self):
        self.assertIsNone(self._revision(stdout=REV + "-dirty\n"))

    def test_command_missing(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(CurrentSystemRevision().running_revision())


if __name__ == "__main__":
    unittest.main()
