import signal
from importlib.resources import as_file, files

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from ..application.services import (
    ChangelogService,
    KernelCheckService,
    UpdateCheckService,
    UpdateStatus,
)
from ..domain.models import Revision
from ..i18n import _
from .windows import RollbackDialog, UpdateWindow
from .workers import UpdateCheckWorker

CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000


class NixOSUpdaterApp(QApplication):
    def __init__(
        self,
        argv: list[str],
        flake_url: str,
        update_service: UpdateCheckService,
        kernel_service: KernelCheckService,
        changelog_service: ChangelogService,
    ) -> None:
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        self._flake_url = flake_url
        self._update_service = update_service
        self._kernel_service = kernel_service
        self._changelog_service = changelog_service
        self._pending_rev: Revision | None = None
        self._post_update = False
        self._update_window: UpdateWindow | None = None
        self._rollback_dialog: RollbackDialog | None = None
        self._worker: UpdateCheckWorker | None = None

        icon = self._app_icon()
        self.setWindowIcon(icon)

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(icon)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.setVisible(False)
        self._rebuild_tray_menu()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_for_update)
        self._timer.start(CHECK_INTERVAL_MS)

        signal.signal(
            signal.SIGUSR1, lambda *_: QTimer.singleShot(0, self._check_for_update)
        )
        QTimer.singleShot(5_000, self._check_for_update)

    def _app_icon(self) -> QIcon:
        try:
            with as_file(files("nixos_updater").joinpath("icon.svg")) as path:
                icon = QIcon(str(path))
                if not icon.isNull():
                    return icon
        except Exception:
            pass
        for name in ("nixos-updater", "nix-snowflake", "system-software-update"):
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                return icon
        return self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)

    def _rebuild_tray_menu(self) -> None:
        menu = self._tray.contextMenu()
        if menu:
            menu.clear()
        else:
            menu = QMenu()
            self._tray.setContextMenu(menu)

        check_action = QAction(_("Check for updates"), self)
        check_action.triggered.connect(self._check_for_update)
        menu.addAction(check_action)

        if self._post_update:
            rollback_action = QAction(_("Rollback if broken"), self)
            rollback_action.triggered.connect(self._show_rollback)
            menu.addAction(rollback_action)

        menu.addSeparator()
        quit_action = QAction(_("Quit"), self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self._pending_rev:
            self._show_update_window()

    def _check_for_update(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._worker = UpdateCheckWorker(self._update_service)
        self._worker.finished.connect(self._on_check_done)
        self._worker.start()

    def _on_check_done(self, result) -> None:
        if result.status == UpdateStatus.UPDATE_AVAILABLE and result.revision:
            self._pending_rev = result.revision
            self._tray.setVisible(True)
            self._tray.showMessage(
                _("System Update Available"),
                _("Click to update your NixOS system."),
                self.windowIcon(),
                5_000,
            )
            self._show_update_window()

    def _show_update_window(self) -> None:
        if self._pending_rev is None:
            return
        if self._update_window is None or self._update_window.rev != self._pending_rev:
            self._update_window = UpdateWindow(
                self._pending_rev,
                self._flake_url,
                self._update_service,
                self._kernel_service,
                self._changelog_service,
            )
            self._update_window.update_completed.connect(self._on_update_completed)
        self._update_window.show()
        self._update_window.raise_()
        self._update_window.activateWindow()

    def _on_update_completed(self, success: bool) -> None:
        if success:
            self._post_update = True
            self._pending_rev = None
            self._rebuild_tray_menu()
            self._tray.setVisible(True)
        else:
            self._tray.setVisible(self._pending_rev is not None or self._post_update)

    def _show_rollback(self) -> None:
        if self._rollback_dialog is None:
            self._rollback_dialog = RollbackDialog(self._update_service)
        self._rollback_dialog.show()
        self._rollback_dialog.raise_()
        self._rollback_dialog.activateWindow()
