import re

from PyQt6.QtCore import QThread, pyqtSignal

from ..application.services import (
    ChangelogService,
    KernelCheckService,
    UpdateCheckResult,
    UpdateCheckService,
)

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


class UpdateCheckWorker(QThread):
    finished = pyqtSignal(object)

    def __init__(self, service: UpdateCheckService) -> None:
        super().__init__()
        self._service = service

    def run(self) -> None:
        self.finished.emit(self._service.check())


class KernelCheckWorker(QThread):
    finished = pyqtSignal(bool)

    def __init__(self, service: KernelCheckService) -> None:
        super().__init__()
        self._service = service

    def run(self) -> None:
        self.finished.emit(self._service.kernel_changed())


class ChangelogWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, service: ChangelogService) -> None:
        super().__init__()
        self._service = service

    def run(self) -> None:
        result = self._service.fetch_diff()
        self.finished.emit(result or "")
