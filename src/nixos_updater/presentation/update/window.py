import subprocess

from PyQt6.QtCore import QEvent, QProcess, Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ...application.services import ChangelogService, KernelCheckService, UpdateCheckService
from ...domain.models import Revision
from ...i18n import _
from ..workers import ChangelogWorker, KernelCheckWorker, _cache_args
from .widgets import ChangelogWidget, LogWidget, ResultWidget


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
        self._changelog_visible = False
        self._log_visible = False
        self._changelog_worker: ChangelogWorker | None = None
        self._setup_ui()
        self._start_kernel_check()
        self._toggle_changelog()

    def _setup_ui(self) -> None:
        self.setWindowTitle(_("System Update Available"))
        self.setWindowFlags(Qt.WindowType.Dialog)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        p = self.palette()
        h      = p.color(QPalette.ColorRole.Highlight)
        ht     = p.color(QPalette.ColorRole.HighlightedText)
        mid    = p.color(QPalette.ColorRole.Mid)
        wt     = p.color(QPalette.ColorRole.WindowText)
        alt    = p.color(QPalette.ColorRole.AlternateBase)
        r, g, b = wt.red(), wt.green(), wt.blue()
        muted  = f"rgba({r},{g},{b},140)"
        # border = midpoint between Mid and Shadow, gives a visible but not harsh line
        border = mid.lighter(130).name()

        self._style_primary = (
            f"QPushButton {{ background:{h.name()}; color:{ht.name()}; border:none;"
            f" border-radius:5px; padding:5px 18px; font-weight:bold; }}"
            f" QPushButton:hover {{ background:{h.lighter(112).name()}; }}"
            f" QPushButton:pressed {{ background:{h.darker(112).name()}; }}"
            f" QPushButton:disabled {{ background:{h.name()};"
            f" color:rgba({ht.red()},{ht.green()},{ht.blue()},100); }}"
        )
        self._style_outline = (
            f"QPushButton {{ background:transparent; border:1px solid {border};"
            f" border-radius:5px; padding:5px 12px; color:{wt.name()}; }}"
            f" QPushButton:hover {{ border-color:{wt.name()}; }}"
        )
        self._style_flat = (
            f"QPushButton {{ background:transparent; border:none; padding:5px 10px;"
            f" color:{muted}; border-radius:5px; }}"
            f" QPushButton:hover {{ background:rgba({r},{g},{b},15); color:{wt.name()}; }}"
        )

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self._title_lbl = QLabel(_("System Update Available"))
        self._apply_title_font()
        rev_chip = QLabel(self.rev.short())
        rev_chip.setStyleSheet(
            f"font-family:monospace; background:{alt.name()}; border-radius:4px;"
            f" padding:2px 8px; color:{muted};"
        )
        header_row.addWidget(self._title_lbl)
        header_row.addStretch()
        header_row.addWidget(rev_chip, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border:none; background:{mid.name()}; max-height:1px;")
        layout.addWidget(sep)

        apply_hdr = QLabel(_("Apply method"))
        apply_hdr.setStyleSheet(f"color:{muted}; font-size:11px; padding:4px 0 2px 0;")
        layout.addWidget(apply_hdr)

        _rb_style = (
            f"QRadioButton {{ color:{wt.name()}; font-weight:bold; spacing:8px; }}"
            f" QRadioButton::indicator {{ width:14px; height:14px; border-radius:8px;"
            f" border:2px solid {border}; background:transparent; }}"
            f" QRadioButton::indicator:checked {{ border-color:{h.name()}; background:{h.name()}; }}"
        )
        _desc_style = f"color:{muted}; padding-left:22px; font-weight:normal;"

        apply_frame = QFrame()
        apply_frame.setObjectName("apply_frame")
        apply_frame.setStyleSheet(
            f"QFrame#apply_frame {{ border:1px solid {border}; border-radius:6px; }}"
        )
        af = QVBoxLayout(apply_frame)
        af.setContentsMargins(14, 10, 14, 10)
        af.setSpacing(1)

        self.radio_switch = QRadioButton(_("Switch — apply now"))
        self.radio_switch.setChecked(True)
        self.radio_switch.setStyleSheet(_rb_style)
        switch_desc = QLabel(_("Reload running services, no reboot required"))
        switch_desc.setStyleSheet(_desc_style)

        self.radio_boot = QRadioButton(_("Boot — on next startup"))
        self.radio_boot.setStyleSheet(_rb_style)
        boot_desc = QLabel(_("Required for kernel or bootloader updates"))
        boot_desc.setStyleSheet(_desc_style)

        self.kernel_warning = QLabel("⚠  " + _("Kernel update detected — boot recommended"))
        self.kernel_warning.setStyleSheet(f"color:{h.name()}; padding-left:22px; padding-top:4px;")
        self.kernel_warning.setVisible(False)

        af.addWidget(self.radio_switch)
        af.addWidget(switch_desc)
        af.addSpacing(6)
        af.addWidget(self.radio_boot)
        af.addWidget(boot_desc)
        af.addWidget(self.kernel_warning)
        layout.addWidget(apply_frame)

        self.changelog_widget = ChangelogWidget()
        self.changelog_widget.setVisible(False)
        layout.addWidget(self.changelog_widget)

        self.log_widget = LogWidget()
        self.log_widget.setVisible(False)
        layout.addWidget(self.log_widget, 100)

        self.result_widget = ResultWidget()
        layout.addWidget(self.result_widget)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.skip_btn = QPushButton(_("Skip Version"))
        self.skip_btn.setStyleSheet(self._style_flat)
        self.skip_btn.clicked.connect(self._on_skip)

        self.later_btn = QPushButton(_("Later"))
        self.later_btn.setStyleSheet(self._style_flat)
        self.later_btn.clicked.connect(self.hide)

        self.changes_btn = QPushButton(_("What's changing?"))
        self.changes_btn.setStyleSheet(self._style_outline)
        self.changes_btn.clicked.connect(self._toggle_changelog)

        self.log_btn = QPushButton(_("Show Log"))
        self.log_btn.setStyleSheet(self._style_outline)
        self.log_btn.clicked.connect(self._toggle_log)

        self.update_btn = QPushButton(_("Update"))
        self.update_btn.setStyleSheet(self._style_primary)
        self.update_btn.setDefault(True)
        self.update_btn.clicked.connect(self._start_update)

        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.later_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.changes_btn)
        btn_row.addWidget(self.log_btn)
        btn_row.addWidget(self.update_btn)
        layout.addLayout(btn_row)

    def _apply_title_font(self) -> None:
        font = self._title_lbl.font()
        font.setPointSizeF(font.pointSizeF() * 1.3)
        font.setBold(True)
        self._title_lbl.setFont(font)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._apply_title_font()

    def _start_kernel_check(self) -> None:
        self._kernel_worker = KernelCheckWorker(self._kernel_service)
        self._kernel_worker.finished.connect(self._on_kernel_check_done)
        self._kernel_worker.start()

    def _on_kernel_check_done(self, changed: bool) -> None:
        if changed:
            self.kernel_warning.setVisible(True)
            self.radio_boot.setChecked(True)

    def _toggle_changelog(self) -> None:
        self._changelog_visible = not self._changelog_visible
        self.changelog_widget.setVisible(self._changelog_visible)
        self.changes_btn.setText(
            _("Hide Changes") if self._changelog_visible else _("What's changing?")
        )
        if self._changelog_visible and not self.changelog_widget.is_populated:
            self._start_changelog()

    def _start_changelog(self) -> None:
        if self._changelog_worker and self._changelog_worker.isRunning():
            return
        self.changelog_widget.set_loading()
        self._changelog_worker = ChangelogWorker(self._changelog_service)
        self._changelog_worker.finished.connect(self.changelog_widget.populate)
        self._changelog_worker.start()

    def _toggle_log(self) -> None:
        self._log_visible = not self._log_visible
        self.log_widget.setVisible(self._log_visible)
        self.log_btn.setText(_("Hide Log") if self._log_visible else _("Show Log"))

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
        success = exit_code == 0
        boot = self.radio_boot.isChecked()
        if success:
            self._update_service.mark_applied(self.rev)
            self.result_widget.show_success(boot=boot)
            if boot:
                self.update_btn.setText(_("Restart Now"))
                self.update_btn.clicked.disconnect()
                self.update_btn.clicked.connect(lambda: subprocess.run(["systemctl", "reboot"]))
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
            self.result_widget.show_failure(exit_code)
            self.update_btn.setText(_("Update"))
            self.update_btn.clicked.disconnect()
            self.update_btn.clicked.connect(self._start_update)
            self.update_btn.setEnabled(True)
            self.later_btn.setText(_("Close"))
            self.later_btn.clicked.disconnect()
            self.later_btn.clicked.connect(self.close)
            self.later_btn.setEnabled(True)
        self.update_completed.emit(success)
