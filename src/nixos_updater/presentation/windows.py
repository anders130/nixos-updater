import subprocess

from PyQt6.QtCore import QProcess, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..application.services import KernelCheckService, UpdateCheckService
from ..domain.models import Revision
from .workers import KernelCheckWorker, strip_ansi


class UpdateWindow(QWidget):
    update_completed = pyqtSignal(bool)

    def __init__(
        self,
        rev: Revision,
        flake_url: str,
        update_service: UpdateCheckService,
        kernel_service: KernelCheckService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.rev = rev
        self._flake_url = flake_url
        self._update_service = update_service
        self._kernel_service = kernel_service
        self._process: QProcess | None = None
        self._log_visible = False
        self._user_scrolled = False
        self._setup_ui()
        self._start_kernel_check()

    def _setup_ui(self) -> None:
        self.setWindowTitle("System Update Available")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("System Update Available")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Revision: {self.rev.short()}"))

        group = QGroupBox("Apply method")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        self.radio_switch = QRadioButton(
            "Apply now (switch)\nSwitch running services without reboot"
        )
        self.radio_switch.setChecked(True)
        self.radio_boot = QRadioButton(
            "Apply on next boot (boot)\nRequired for kernel / bootloader changes"
        )
        self.kernel_warning = QLabel("Kernel update detected — boot recommended")
        self.kernel_warning.setStyleSheet("color: orange;")
        self.kernel_warning.setVisible(False)
        group_layout.addWidget(self.radio_switch)
        group_layout.addWidget(self.radio_boot)
        group_layout.addWidget(self.kernel_warning)
        layout.addWidget(group)

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
        self.skip_btn = QPushButton("Skip Version")
        self.skip_btn.clicked.connect(self._on_skip)
        self.later_btn = QPushButton("Later")
        self.later_btn.clicked.connect(self.hide)
        self.log_btn = QPushButton("Show Log")
        self.log_btn.clicked.connect(self._toggle_log)
        self.update_btn = QPushButton("Update")
        self.update_btn.setDefault(True)
        self.update_btn.clicked.connect(self._start_update)
        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.later_btn)
        btn_row.addStretch()
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

    def _toggle_log(self) -> None:
        self._log_visible = not self._log_visible
        self.log_edit.setVisible(self._log_visible)
        self.log_btn.setText("Hide Log" if self._log_visible else "Show Log")
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
        self._append_log(f"$ {' '.join(cmd)}\n")

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
            self._append_log("\nUpdate successful!")
            if self.radio_boot.isChecked():
                self._append_log(
                    "Restart to apply the new kernel / bootloader changes."
                )
                self.update_btn.setText("Restart Now")
                self.update_btn.clicked.disconnect()
                self.update_btn.clicked.connect(
                    lambda: subprocess.run(["systemctl", "reboot"])
                )
                self.update_btn.setEnabled(True)
                self.later_btn.setText("Close")
                self.later_btn.clicked.disconnect()
                self.later_btn.clicked.connect(self.close)
                self.later_btn.setEnabled(True)
            else:
                self.update_btn.setText("Close")
                self.update_btn.clicked.disconnect()
                self.update_btn.clicked.connect(self.close)
                self.update_btn.setEnabled(True)
                self.later_btn.setVisible(False)
        else:
            self._append_log(f"\nUpdate failed (exit code {exit_code})")
            self.update_btn.setText("Update")
            self.update_btn.clicked.disconnect()
            self.update_btn.clicked.connect(self._start_update)
            self.update_btn.setEnabled(True)
            self.later_btn.setText("Close")
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
        self.setWindowTitle("Rollback System")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel("Roll back to the previous system configuration?"))

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
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.hide)
        self.rollback_btn = QPushButton("Rollback")
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
        self._append_log(f"$ {' '.join(cmd)}\n")

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
        if exit_code == 0:
            self._update_service.clear_applied()
            self._append_log("\nRollback successful!")
        else:
            self._append_log(f"\nRollback failed (exit code {exit_code})")
        self.cancel_btn.setText("Close")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.close)
        self.cancel_btn.setEnabled(True)
