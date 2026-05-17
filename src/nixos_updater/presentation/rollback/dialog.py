from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...application.services import UpdateCheckService
from ...i18n import _
from ..update.widgets import LogWidget
from ..workers import _cache_args


class RollbackDialog(QWidget):
    def __init__(self, update_service: UpdateCheckService, parent=None) -> None:
        super().__init__(parent)
        self._update_service = update_service
        self._process: QProcess | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(_("Rollback System"))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel(_("Roll back to the previous system configuration?")))

        self.log_widget = LogWidget()
        self.log_widget.setVisible(False)
        layout.addWidget(self.log_widget, stretch=100)

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

    def _start_rollback(self) -> None:
        self.rollback_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.log_widget.setVisible(True)

        cmd = ["sudo", "nixos-rebuild", "switch", "--rollback"]
        self.log_widget.append_command(cmd)
        cmd += _cache_args()

        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.start(cmd[0], cmd[1:])

    def _read_output(self) -> None:
        assert self._process is not None
        raw = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.log_widget.append_output(raw)

    def _on_finished(self, exit_code: int, _status) -> None:
        if exit_code == 0:
            self._update_service.clear_applied()
            self.log_widget.append_output(_("\nRollback successful!"))
        else:
            self.log_widget.append_output(_("\nRollback failed (exit code %d)") % exit_code)
        self.cancel_btn.setText(_("Close"))
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.close)
        self.cancel_btn.setEnabled(True)
