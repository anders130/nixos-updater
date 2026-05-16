import os
import re
import subprocess

from PyQt6.QtCore import QModelIndex, QProcess, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QCursor, QDesktopServices
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..application.services import (
    ChangelogService,
    KernelCheckService,
    UpdateCheckService,
)
from ..domain.models import Revision
from ..i18n import _
from .workers import ChangelogWorker, HomepageWorker, KernelCheckWorker, strip_ansi


def _cache_args() -> list[str]:
    args = []
    for entry in os.environ.get("NIXOS_UPDATER_CACHES", "").split(";"):
        parts = entry.split("|", 1)
        if len(parts) == 2 and parts[0].strip():
            args += [
                "--substituters",
                parts[0].strip(),
                "--trusted-public-keys",
                parts[1].strip(),
            ]
    return args


class UpdateWindow(QWidget):
    update_completed = pyqtSignal(bool)

    def __init__(
        self,
        rev: Revision,
        flake_url: str,
        update_service: UpdateCheckService,
        kernel_service: KernelCheckService,
        changelog_service: ChangelogService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.rev = rev
        self._flake_url = flake_url
        self._update_service = update_service
        self._kernel_service = kernel_service
        self._changelog_service = changelog_service
        self._process: QProcess | None = None
        self._log_visible = False
        self._changelog_visible = False
        self._user_scrolled = False
        self._changelog_worker: ChangelogWorker | None = None
        self._homepage_worker: HomepageWorker | None = None
        self._setup_ui()
        self._start_kernel_check()
        self._toggle_changelog()

    def _setup_ui(self) -> None:
        self.setWindowTitle(_("System Update Available"))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(_("System Update Available"))
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel(_("Revision: %s") % self.rev.short()))

        group = QGroupBox(_("Apply method"))
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        self.radio_switch = QRadioButton(
            _("Apply now (switch)\nSwitch running services without reboot")
        )
        self.radio_switch.setChecked(True)
        self.radio_boot = QRadioButton(
            _("Apply on next boot (boot)\nRequired for kernel / bootloader changes")
        )
        self.kernel_warning = QLabel(_("Kernel update detected — boot recommended"))
        self.kernel_warning.setStyleSheet("color: orange;")
        self.kernel_warning.setVisible(False)
        group_layout.addWidget(self.radio_switch)
        group_layout.addWidget(self.radio_boot)
        group_layout.addWidget(self.kernel_warning)
        layout.addWidget(group)

        self.changelog_tree = QTreeWidget()
        self.changelog_tree.setVisible(False)
        self.changelog_tree.setMinimumHeight(150)
        self.changelog_tree.setMaximumHeight(300)
        self.changelog_tree.setColumnCount(4)
        self.changelog_tree.setHeaderLabels(
            [_("Package"), _("Old"), _("New"), _("Size")]
        )
        self.changelog_tree.setRootIsDecorated(True)
        self.changelog_tree.header().setStretchLastSection(True)
        self.changelog_tree.itemDoubleClicked.connect(self._on_changelog_item_activated)
        layout.addWidget(self.changelog_tree, stretch=1)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setVisible(False)
        self.log_edit.setMinimumHeight(180)
        font = self.log_edit.font()
        font.setFamily("monospace")
        self.log_edit.setFont(font)
        self.log_edit.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.log_edit, stretch=1)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.skip_btn = QPushButton(_("Skip Version"))
        self.skip_btn.clicked.connect(self._on_skip)
        self.later_btn = QPushButton(_("Later"))
        self.later_btn.clicked.connect(self.hide)
        self.changes_btn = QPushButton(_("What's changing?"))
        self.changes_btn.clicked.connect(self._toggle_changelog)
        self.log_btn = QPushButton(_("Show Log"))
        self.log_btn.clicked.connect(self._toggle_log)
        self.update_btn = QPushButton(_("Update"))
        self.update_btn.setDefault(True)
        self.update_btn.clicked.connect(self._start_update)
        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.later_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.changes_btn)
        btn_row.addWidget(self.log_btn)
        btn_row.addWidget(self.update_btn)
        layout.addLayout(btn_row)

    def _start_kernel_check(self) -> None:
        self._kernel_worker = KernelCheckWorker(self._kernel_service)
        self._kernel_worker.finished.connect(self._on_kernel_check_done)
        self._kernel_worker.start()

    def _on_kernel_check_done(self, changed: bool) -> None:
        if changed:
            self.kernel_warning.setVisible(True)
            self.radio_boot.setChecked(True)

    def _on_changelog_item_activated(self, item: QTreeWidgetItem, _col: int) -> None:
        if item.parent() is None:
            return
        if self._homepage_worker and self._homepage_worker.isRunning():
            return
        name = item.text(0)
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        self._homepage_worker = HomepageWorker(name)
        self._homepage_worker.finished.connect(self._on_homepage_fetched)
        self._homepage_worker.start()

    def _on_homepage_fetched(self, url: str) -> None:
        self.unsetCursor()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _toggle_changelog(self) -> None:
        self._changelog_visible = not self._changelog_visible
        self.changelog_tree.setVisible(self._changelog_visible)
        self.changes_btn.setText(
            _("Hide Changes") if self._changelog_visible else _("What's changing?")
        )
        if self._changelog_visible and self.changelog_tree.topLevelItemCount() == 0:
            self._start_changelog()
        self.adjustSize()

    def _start_changelog(self) -> None:
        if self._changelog_worker and self._changelog_worker.isRunning():
            return
        placeholder = QTreeWidgetItem([_("Building closure, please wait…")])
        placeholder.setForeground(0, QBrush(QColor(150, 150, 150)))
        self.changelog_tree.clear()
        self.changelog_tree.addTopLevelItem(placeholder)
        self._changelog_worker = ChangelogWorker(self._changelog_service)
        self._changelog_worker.finished.connect(self._on_changelog_done)
        self._changelog_worker.start()

    def _on_changelog_done(self, result: str) -> None:
        self.changelog_tree.clear()
        if not result.strip():
            self.changelog_tree.addTopLevelItem(
                QTreeWidgetItem([_("No package changes detected.")])
            )
            return
        self._populate_changelog(result)

    @staticmethod
    def _bump_level(old: str, new: str) -> str:
        def parts(v):
            return [int(x) for x in re.findall(r"\d+", v)]

        o, n = parts(old), parts(new)
        if not o or not n:
            return "minor"
        if o[0] != n[0]:
            return "major"
        if len(o) > 1 and len(n) > 1 and o[1] != n[1]:
            return "minor"
        return "patch"

    @staticmethod
    def _parse_diff(raw: str):
        changed_re = re.compile(r"^(.+?):\s+(.+?)\s+→\s+(.+?)(?:,\s+(.+))?\s*$")
        added_re = re.compile(r"^(.+?):\s+\(new\)(?:,\s+(.+))?\s*$")
        updated, added, removed = [], [], []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            m = added_re.match(line)
            if m:
                added.append((m.group(1), "", "", m.group(2) or ""))
                continue
            m = changed_re.match(line)
            if m:
                name, old, new, size = (
                    m.group(1),
                    m.group(2),
                    m.group(3),
                    m.group(4) or "",
                )
                if "(gone)" in new:
                    removed.append((name, old, "", size))
                else:
                    updated.append((name, old, new, size))
        level_order = {"major": 0, "minor": 1, "patch": 2}
        updated.sort(key=lambda t: level_order[UpdateWindow._bump_level(t[1], t[2])])
        return updated, added, removed

    def _populate_changelog(self, raw: str) -> None:
        updated, added, removed = self._parse_diff(raw)

        def add_section(label, items, base_color, check_level=False):
            if not items:
                return
            header = QTreeWidgetItem([f"{label}  ({len(items)})"])
            font = header.font(0)
            font.setBold(True)
            header.setFont(0, font)
            header.setForeground(0, QBrush(base_color))
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.changelog_tree.addTopLevelItem(header)
            idx = self.changelog_tree.indexOfTopLevelItem(header)
            self.changelog_tree.setFirstColumnSpanned(idx, QModelIndex(), True)
            for name, old, new, size in items:
                if check_level:
                    level = self._bump_level(old, new)
                    if level == "major":
                        color = QColor(86, 156, 214)
                    elif level == "minor":
                        color = QColor(120, 180, 220)
                    else:
                        color = QColor(160, 200, 230)
                else:
                    color = base_color
                row = QTreeWidgetItem(header, [name, old, new, size])
                font = row.font(0)
                font.setBold(level == "major" if check_level else False)
                row.setFont(0, font)
                for col in range(4):
                    row.setForeground(col, QBrush(color))
            header.setExpanded(True)

        add_section(_("Updated"), updated, QColor(86, 156, 214), check_level=True)
        add_section(_("Added"), added, QColor(100, 200, 100))
        add_section(_("Removed"), removed, QColor(220, 80, 80))

        for i in range(3):
            self.changelog_tree.resizeColumnToContents(i)

    def _toggle_log(self) -> None:
        self._log_visible = not self._log_visible
        self.log_edit.setVisible(self._log_visible)
        self.log_btn.setText(_("Hide Log") if self._log_visible else _("Show Log"))
        self.adjustSize()

    def _on_scroll(self, value: int) -> None:
        self._user_scrolled = value < self.log_edit.verticalScrollBar().maximum()

    def _append_log(self, text: str) -> None:
        for line in strip_ansi(text).splitlines():
            self.log_edit.appendPlainText(line)
        if not self._user_scrolled:
            sb = self.log_edit.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_skip(self) -> None:
        self._update_service.mark_skipped(self.rev)
        self.hide()

    def _start_update(self) -> None:
        action = "boot" if self.radio_boot.isChecked() else "switch"
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.radio_switch.setEnabled(False)
        self.radio_boot.setEnabled(False)
        if not self._log_visible:
            self._toggle_log()

        cmd = ["sudo", "nixos-rebuild", action, "--flake", self._flake_url]
        self._append_log(_("$ %s\n") % " ".join(cmd))
        cmd += _cache_args()

        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.start(cmd[0], cmd[1:])

    def _read_output(self) -> None:
        assert self._process is not None
        raw = (
            self._process.readAllStandardOutput()
            .data()
            .decode("utf-8", errors="replace")
        )
        self._append_log(raw)

    def _on_finished(self, exit_code: int, _) -> None:
        success = exit_code == 0
        if success:
            self._update_service.mark_applied(self.rev)
            self._append_log(_("\nUpdate successful!"))
            if self.radio_boot.isChecked():
                self._append_log(
                    _("Restart to apply the new kernel / bootloader changes.")
                )
                self.update_btn.setText(_("Restart Now"))
                self.update_btn.clicked.disconnect()
                self.update_btn.clicked.connect(
                    lambda: subprocess.run(["systemctl", "reboot"])
                )
                self.update_btn.setEnabled(True)
                self.later_btn.setText(_("Close"))
                self.later_btn.clicked.disconnect()
                self.later_btn.clicked.connect(self.close)
                self.later_btn.setEnabled(True)
            else:
                self.update_btn.setText(_("Close"))
                self.update_btn.clicked.disconnect()
                self.update_btn.clicked.connect(self.close)
                self.update_btn.setEnabled(True)
                self.later_btn.setVisible(False)
        else:
            self._append_log(_("\nUpdate failed (exit code %d)") % exit_code)
            self.update_btn.setText(_("Update"))
            self.update_btn.clicked.disconnect()
            self.update_btn.clicked.connect(self._start_update)
            self.update_btn.setEnabled(True)
            self.later_btn.setText(_("Close"))
            self.later_btn.clicked.disconnect()
            self.later_btn.clicked.connect(self.close)
            self.later_btn.setEnabled(True)
        self.update_completed.emit(success)


class RollbackDialog(QWidget):
    def __init__(self, update_service: UpdateCheckService, parent=None) -> None:
        super().__init__(parent)
        self._update_service = update_service
        self._process: QProcess | None = None
        self._user_scrolled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(_("Rollback System"))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel(_("Roll back to the previous system configuration?")))

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setVisible(False)
        self.log_edit.setMinimumHeight(180)
        font = self.log_edit.font()
        font.setFamily("monospace")
        self.log_edit.setFont(font)
        self.log_edit.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.log_edit, stretch=1)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.hide)
        self.rollback_btn = QPushButton(_("Rollback"))
        self.rollback_btn.setDefault(True)
        self.rollback_btn.clicked.connect(self._start_rollback)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.rollback_btn)
        layout.addLayout(btn_row)

    def _on_scroll(self, value: int) -> None:
        self._user_scrolled = value < self.log_edit.verticalScrollBar().maximum()

    def _append_log(self, text: str) -> None:
        for line in strip_ansi(text).splitlines():
            self.log_edit.appendPlainText(line)
        if not self._user_scrolled:
            sb = self.log_edit.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _start_rollback(self) -> None:
        self.rollback_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.log_edit.setVisible(True)

        cmd = ["sudo", "nixos-rebuild", "switch", "--rollback"]
        self._append_log(_("$ %s\n") % " ".join(cmd))
        cmd += _cache_args()

        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.start(cmd[0], cmd[1:])

    def _read_output(self) -> None:
        assert self._process is not None
        raw = (
            self._process.readAllStandardOutput()
            .data()
            .decode("utf-8", errors="replace")
        )
        self._append_log(raw)

    def _on_finished(self, exit_code: int, _status) -> None:
        if exit_code == 0:
            self._update_service.clear_applied()
            self._append_log(_("\nRollback successful!"))
        else:
            self._append_log(_("\nRollback failed (exit code %d)") % exit_code)
        self.cancel_btn.setText(_("Close"))
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.close)
        self.cancel_btn.setEnabled(True)
