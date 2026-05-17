import os
import re
import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal

from ..application.services import ChangelogService, KernelCheckService, UpdateCheckService


def _cache_args() -> list[str]:
    args = []
    for entry in os.environ.get("NIXOS_UPDATER_CACHES", "").split(";"):
        parts = entry.split("|", 1)
        if len(parts) == 2 and parts[0].strip():
            args += ["--substituters", parts[0].strip(), "--trusted-public-keys", parts[1].strip()]
    return args

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


class HomepageWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, package: str) -> None:
        super().__init__()
        self._package = package

    def run(self) -> None:
        try:
            result = subprocess.run(
                ["nix", "eval", "--raw", f"nixpkgs#{self._package}.meta.homepage"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.finished.emit(result.stdout.strip() if result.returncode == 0 else "")
        except Exception as e:
            print(f"HomepageWorker: {e}", file=sys.stderr)
            self.finished.emit("")
