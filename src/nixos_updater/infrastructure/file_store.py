from pathlib import Path

from ..domain.models import Revision
from ..domain.ports import RevisionStore


class FileRevisionStore(RevisionStore):
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir
        self._applied = data_dir / "applied-rev"
        self._skipped = data_dir / "skipped-rev"

    def get_applied(self) -> Revision | None:
        return self._read(self._applied)

    def get_skipped(self) -> Revision | None:
        return self._read(self._skipped)

    def save_applied(self, rev: Revision) -> None:
        self._write(self._applied, rev)

    def save_skipped(self, rev: Revision) -> None:
        self._write(self._skipped, rev)

    def clear_applied(self) -> None:
        if self._applied.exists():
            self._applied.unlink()

    def _read(self, path: Path) -> Revision | None:
        if path.exists():
            text = path.read_text().strip()
            if text:
                return Revision(text)
        return None

    def _write(self, path: Path, rev: Revision) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path.write_text(rev.value)
