from abc import ABC, abstractmethod

from .models import KernelVersion, Revision


class RevisionStore(ABC):
    @abstractmethod
    def get_applied(self) -> Revision | None: ...

    @abstractmethod
    def get_skipped(self) -> Revision | None: ...

    @abstractmethod
    def save_applied(self, rev: Revision) -> None: ...

    @abstractmethod
    def save_skipped(self, rev: Revision) -> None: ...

    @abstractmethod
    def clear_applied(self) -> None: ...


class FlakeSource(ABC):
    @abstractmethod
    def fetch_revision(self) -> Revision | None: ...


class KernelInspector(ABC):
    @abstractmethod
    def running_version(self) -> KernelVersion | None: ...

    @abstractmethod
    def upstream_version(self) -> KernelVersion | None: ...


class SystemDiffer(ABC):
    @abstractmethod
    def diff(self) -> str | None: ...
