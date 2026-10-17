import unittest

from nixos_updater.application.services import UpdateCheckService, UpdateStatus
from nixos_updater.domain.models import Revision
from nixos_updater.domain.ports import FlakeSource, RevisionStore, RunningRevisionSource

REMOTE = Revision("b" * 40)
OTHER = Revision("a" * 40)


class _Store(RevisionStore):
    def __init__(self, applied=None, skipped=None) -> None:
        self.applied = applied
        self.skipped = skipped

    def get_applied(self):
        return self.applied

    def get_skipped(self):
        return self.skipped

    def save_applied(self, rev):
        self.applied = rev

    def save_skipped(self, rev):
        self.skipped = rev

    def clear_applied(self):
        self.applied = None


class _Source(FlakeSource):
    def __init__(self, rev) -> None:
        self._rev = rev

    def fetch_revision(self):
        return self._rev


class _Running(RunningRevisionSource):
    def __init__(self, rev) -> None:
        self._rev = rev

    def running_revision(self):
        return self._rev


def _check(running, store, remote=REMOTE):
    return UpdateCheckService(store, _Source(remote), _Running(running)).check()


class UpdateCheckTest(unittest.TestCase):
    def test_running_matches_remote(self):
        result = _check(REMOTE, _Store())
        self.assertEqual(result.status, UpdateStatus.UP_TO_DATE)

    def test_running_differs_from_remote(self):
        result = _check(OTHER, _Store())
        self.assertEqual(result.status, UpdateStatus.UPDATE_AVAILABLE)
        self.assertEqual(result.revision, REMOTE)

    def test_running_wins_over_stale_applied(self):
        # Host deployed by hand: applied-rev is stale but the system runs REMOTE.
        result = _check(REMOTE, _Store(applied=OTHER))
        self.assertEqual(result.status, UpdateStatus.UP_TO_DATE)

    def test_running_wins_over_matching_applied(self):
        result = _check(OTHER, _Store(applied=REMOTE))
        self.assertEqual(result.status, UpdateStatus.UPDATE_AVAILABLE)

    def test_skipped_remote(self):
        result = _check(OTHER, _Store(skipped=REMOTE))
        self.assertEqual(result.status, UpdateStatus.UP_TO_DATE)

    def test_unknown_running_falls_back_to_applied(self):
        self.assertEqual(
            _check(None, _Store(applied=REMOTE)).status, UpdateStatus.UP_TO_DATE
        )
        self.assertEqual(
            _check(None, _Store(applied=OTHER)).status, UpdateStatus.UPDATE_AVAILABLE
        )

    def test_unknown_running_without_applied(self):
        store = _Store()
        result = _check(None, store)
        self.assertEqual(result.status, UpdateStatus.UPDATE_AVAILABLE)
        self.assertIsNone(store.applied)

    def test_remote_unreachable(self):
        result = _check(OTHER, _Store(), remote=None)
        self.assertEqual(result.status, UpdateStatus.UP_TO_DATE)


if __name__ == "__main__":
    unittest.main()
