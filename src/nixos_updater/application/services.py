from dataclasses import dataclass
from enum import Enum, auto

from ..domain.models import Revision
from ..domain.ports import FlakeSource, KernelInspector, RevisionStore, SystemDiffer


class UpdateStatus(Enum):
    UP_TO_DATE = auto()
    UPDATE_AVAILABLE = auto()


@dataclass
class UpdateCheckResult:
    status: UpdateStatus
    revision: Revision | None = None


class UpdateCheckService:
    def __init__(self, store: RevisionStore, source: FlakeSource) -> None:
        self._store = store
        self._source = source

    def check(self) -> UpdateCheckResult:
        revision = self._source.fetch_revision()
        if revision is None:
            return UpdateCheckResult(UpdateStatus.UP_TO_DATE)

        applied = self._store.get_applied()
        if applied is None:
            self._store.save_applied(revision)
            return UpdateCheckResult(UpdateStatus.UP_TO_DATE)

        skipped = self._store.get_skipped()
        if revision.value in {applied.value, skipped.value if skipped else None}:
            return UpdateCheckResult(UpdateStatus.UP_TO_DATE)

        return UpdateCheckResult(UpdateStatus.UPDATE_AVAILABLE, revision)

    def mark_applied(self, rev: Revision) -> None:
        self._store.save_applied(rev)

    def mark_skipped(self, rev: Revision) -> None:
        self._store.save_skipped(rev)

    def clear_applied(self) -> None:
        self._store.clear_applied()


class KernelCheckService:
    def __init__(self, inspector: KernelInspector) -> None:
        self._inspector = inspector

    def kernel_changed(self) -> bool:
        running = self._inspector.running_version()
        if running is None:
            return False
        upstream = self._inspector.upstream_version()
        return upstream is not None and upstream.value != running.value


class ChangelogService:
    def __init__(self, differ: SystemDiffer) -> None:
        self._differ = differ

    def fetch_diff(self) -> str | None:
        return self._differ.diff()
